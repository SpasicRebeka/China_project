"""Stream microphone audio to realtime transcription with local noise handling."""

from __future__ import annotations

import argparse
import base64
import math
import queue
import re
import signal
import sys
import threading
import time
from array import array
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import sounddevice as sd
from openai import OpenAI

from config import (
    get_openai_api_key,
    get_realtime_transcription_delay,
    get_realtime_transcription_model,
    load_project_environment,
)


SAMPLE_RATE = 24_000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2
REALTIME_WHISPER_MODEL = "gpt-realtime-whisper"
DEFAULT_MEDICAL_TRANSCRIPTION_PROMPT = (
    "Doctor-patient hospital conversation. Transcribe the spoken words literally. "
    "Use medical vocabulary only when it is actually spoken. Expect symptoms, body parts, "
    "blood pressure, heart rate, oxygen saturation, temperature, medication names, dosages, "
    "allergies, follow-up dates, and simple clinical instructions. Do not summarize, "
    "translate, explain, complete unfinished sentences, or add missing words."
)
WORD_PATTERN = re.compile(r"[^\W_]+(?:'[^\W_]+)?", re.UNICODE)
MID_SENTENCE_LOWERCASE_STARTS = {
    "a",
    "about",
    "after",
    "also",
    "am",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "down",
    "for",
    "from",
    "go",
    "had",
    "has",
    "have",
    "he",
    "her",
    "here",
    "him",
    "his",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "like",
    "listen",
    "look",
    "make",
    "may",
    "might",
    "must",
    "need",
    "no",
    "not",
    "of",
    "on",
    "or",
    "over",
    "say",
    "see",
    "shall",
    "she",
    "should",
    "so",
    "take",
    "tell",
    "than",
    "that",
    "the",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "under",
    "up",
    "use",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "while",
    "who",
    "why",
    "will",
    "with",
    "without",
    "would",
    "yes",
    "you",
    "your",
}
SENTENCE_ENDINGS = ".!?。！？"


class Pcm16MonoResampler:
    """Small streaming linear resampler for mono 16-bit PCM."""

    def __init__(self, source_rate: int, target_rate: int = SAMPLE_RATE) -> None:
        self.source_rate = source_rate
        self.target_rate = target_rate
        self.step = source_rate / target_rate
        self.position = 0.0
        self.buffer = array("h")

    def process(self, audio_bytes: bytes) -> bytes:
        if self.source_rate == self.target_rate:
            return audio_bytes

        incoming = array("h")
        incoming.frombytes(audio_bytes)
        if sys.byteorder != "little":
            incoming.byteswap()
        self.buffer.extend(incoming)

        output = array("h")
        while self.position + 1 < len(self.buffer):
            left_index = int(self.position)
            right_index = left_index + 1
            fraction = self.position - left_index
            left = self.buffer[left_index]
            right = self.buffer[right_index]
            sample = round(left + (right - left) * fraction)
            output.append(max(-32768, min(32767, sample)))
            self.position += self.step

        drop_count = max(0, int(self.position) - 1)
        if drop_count:
            del self.buffer[:drop_count]
            self.position -= drop_count

        return output.tobytes()


@dataclass
class NoiseGateState:
    """Track local speech detection and commit boundaries."""

    threshold: float
    silence_frames_to_commit: int
    min_speech_frames: int
    max_speech_frames: int
    prefix_frames: int
    enabled: bool = True

    in_speech: bool = False
    speech_frames: int = 0
    silent_frames: int = 0


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream microphone audio to OpenAI realtime transcription."
    )
    parser.add_argument("--list-devices", action="store_true", help="Show available audio devices.")
    parser.add_argument("--device", help="Input device index or name. Defaults to the system input.")
    parser.add_argument(
        "--language",
        default="zh",
        help="Input language as ISO-639-1, for example zh or en. Defaults to zh.",
    )
    parser.add_argument(
        "--mode",
        choices=["quiet-room", "low-latency"],
        default="quiet-room",
        help="quiet-room uses server VAD for complete sentences; low-latency uses rolling chunks.",
    )
    parser.add_argument(
        "--transcription-model",
        default=get_realtime_transcription_model(),
        help="Realtime transcription model. Defaults to REALTIME_TRANSCRIPTION_MODEL.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_MEDICAL_TRANSCRIPTION_PROMPT,
        help=(
            "Prompt hint for medical dictation vocabulary. Used by realtime "
            "transcription models that support prompts."
        ),
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="Stop automatically after this many seconds. Omit to run until Ctrl+C.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Save completed transcript lines to this UTF-8 file.",
    )
    parser.add_argument(
        "--delay",
        choices=["minimal", "low", "medium", "high", "xhigh"],
        default=get_realtime_transcription_delay(),
        help="Realtime transcription delay. Minimal is fastest; higher can improve accuracy.",
    )
    parser.add_argument(
        "--noise-reduction",
        choices=["near_field", "far_field", "off"],
        default="near_field",
        help="Cloud input noise reduction. Use near_field for a close directional mic.",
    )
    parser.add_argument(
        "--vad-threshold",
        type=float,
        default=0.35,
        help="Server VAD threshold for quiet-room mode. Lower is more sensitive.",
    )
    parser.add_argument(
        "--calibrate-seconds",
        type=float,
        default=1.5,
        help="Seconds used to measure room noise before streaming speech.",
    )
    parser.add_argument(
        "--noise-multiplier",
        type=float,
        default=3.0,
        help="Speech threshold multiplier above calibrated room noise.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        help="Manual RMS speech threshold. Overrides calibration.",
    )
    parser.add_argument(
        "--min-threshold",
        type=float,
        default=120.0,
        help="Lowest automatic RMS threshold after calibration.",
    )
    parser.add_argument(
        "--silence-ms",
        type=int,
        default=650,
        help="Silence duration before committing one speech segment.",
    )
    parser.add_argument(
        "--prefix-ms",
        type=int,
        default=500,
        help="Audio kept before speech starts so first words are not clipped.",
    )
    parser.add_argument(
        "--min-utterance-ms",
        type=int,
        default=120,
        help="Ignore speech bursts shorter than this.",
    )
    parser.add_argument(
        "--max-segment-seconds",
        type=float,
        default=1.2,
        help="Force a commit after this much continuous speech.",
    )
    parser.add_argument(
        "--block-ms",
        type=int,
        default=20,
        help="Microphone chunk size in milliseconds. Lower can reduce latency.",
    )
    parser.add_argument(
        "--local-noise-gate",
        action="store_true",
        help="Only stream audio above the calibrated speech threshold.",
    )
    parser.add_argument(
        "--no-local-noise-gate",
        dest="local_noise_gate",
        action="store_false",
        help="Stream all microphone audio and commit on timed segments. This is the default.",
    )
    parser.add_argument(
        "--monitor-levels",
        action="store_true",
        help="Show microphone RMS levels without connecting to OpenAI.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print realtime event and local speech-gate diagnostics.",
    )
    parser.add_argument(
        "--final-wait-seconds",
        type=float,
        default=5.0,
        help="Wait this long for final transcripts after stopping.",
    )
    parser.set_defaults(local_noise_gate=False)
    return parser.parse_args()


def list_devices() -> None:
    print(sd.query_devices())


def parse_device(device: str | None) -> int | str | None:
    if device is None:
        return None
    try:
        return int(device)
    except ValueError:
        return device


def get_input_sample_rate(device: int | str | None) -> int:
    device_info = sd.query_devices(device, "input")
    return int(device_info["default_samplerate"])


def rms_level(audio_bytes: bytes) -> float:
    samples = array("h")
    samples.frombytes(audio_bytes)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return 0.0
    square_sum = sum(sample * sample for sample in samples)
    return math.sqrt(square_sum / len(samples))


def ms_to_frames(ms: int, block_ms: int) -> int:
    return max(1, math.ceil(ms / block_ms))


def build_session_update(args: argparse.Namespace) -> dict:
    noise_reduction = None
    if args.noise_reduction != "off":
        noise_reduction = {"type": args.noise_reduction}

    transcription = {
        "model": args.transcription_model,
        "language": args.language,
    }
    if args.transcription_model == REALTIME_WHISPER_MODEL:
        transcription["delay"] = args.delay
    elif args.prompt:
        transcription["prompt"] = args.prompt

    turn_detection = None
    if should_use_server_vad(args):
        turn_detection = {
            "type": "server_vad",
            "threshold": args.vad_threshold,
            "prefix_padding_ms": args.prefix_ms,
            "silence_duration_ms": args.silence_ms,
        }

    return {
        "type": "session.update",
        "session": {
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                    "noise_reduction": noise_reduction,
                    "transcription": transcription,
                    "turn_detection": turn_detection,
                }
            },
        },
    }


def should_use_server_vad(args: argparse.Namespace) -> bool:
    return args.mode == "quiet-room" and args.transcription_model != REALTIME_WHISPER_MODEL


def audio_callback_factory(audio_queue: queue.Queue[bytes], stop_event: threading.Event):
    def callback(indata, frames, time_info, status) -> None:
        if status:
            print(f"\nAudio warning: {status}", file=sys.stderr)
        if stop_event.is_set():
            return
        try:
            audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            try:
                audio_queue.get_nowait()
                audio_queue.put_nowait(bytes(indata))
            except queue.Empty:
                pass

    return callback


def calibrate_noise(
    audio_queue: queue.Queue[bytes],
    resampler: Pcm16MonoResampler,
    seconds: float,
    block_seconds: float,
    min_threshold: float,
    multiplier: float,
) -> float:
    frames_needed = max(1, math.ceil(seconds / block_seconds))
    levels: list[float] = []

    print(f"Calibrating room noise for {seconds:.1f}s. Stay quiet near the microphone...")
    while len(levels) < frames_needed:
        raw_audio = audio_queue.get()
        audio_bytes = resampler.process(raw_audio)
        if not audio_bytes:
            continue
        levels.append(rms_level(audio_bytes))

    average_noise = sum(levels) / len(levels)
    threshold = max(min_threshold, average_noise * multiplier)
    print(f"Room noise RMS: {average_noise:.1f}; speech threshold: {threshold:.1f}")
    return threshold


def send_audio(connection, audio_bytes: bytes) -> None:
    encoded_audio = base64.b64encode(audio_bytes).decode("ascii")
    connection.input_audio_buffer.append(audio=encoded_audio)


def commit_buffer(connection) -> None:
    try:
        connection.input_audio_buffer.commit()
    except Exception as error:
        print(f"\nCommit warning: {error}", file=sys.stderr)
        try:
            connection.input_audio_buffer.clear()
        except Exception:
            pass


def wait_for_session_ready(connection, debug: bool = False) -> None:
    """Wait until the server confirms the transcription session settings."""
    while True:
        event = connection.recv()
        event_type = getattr(event, "type", "")
        if debug:
            print(f"\n[event] {event_type}")
        if event_type == "session.updated":
            return
        if event_type == "error":
            raise RuntimeError(getattr(event, "error", event))


def drain_audio_queue(audio_queue: queue.Queue[bytes]) -> None:
    while True:
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            return


def transcript_separator(current_text: str, next_text: str) -> str:
    """Choose a separator for appending one transcript part to another."""
    if not current_text or not next_text:
        return ""

    previous = current_text[-1]
    next_character = next_text[0]
    if previous.isspace() or next_character.isspace():
        return ""
    if _is_cjk_or_fullwidth(previous) or _is_cjk_or_fullwidth(next_character):
        return ""
    if previous in "([{/\\-" or next_character in ".,;:!?)]}%/\\-":
        return ""
    return " "


def _is_cjk_or_fullwidth(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3000 <= codepoint <= 0x303F
        or 0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0xFF00 <= codepoint <= 0xFFEF
        or 0x20000 <= codepoint <= 0x2EBEF
    )


def _contains_cjk_or_fullwidth(text: str) -> bool:
    return any(_is_cjk_or_fullwidth(character) for character in text)


def _word_spans(text: str) -> list[tuple[str, int, int]]:
    return [
        (match.group(0).casefold(), match.start(), match.end())
        for match in WORD_PATTERN.finditer(text)
    ]


def _suffix_prefix_overlap_length(current_text: str, next_text: str) -> int:
    current_text = current_text.rstrip()
    next_text = next_text.lstrip()
    max_overlap = min(80, len(current_text), len(next_text))

    for length in range(max_overlap, 0, -1):
        current_suffix = current_text[-length:]
        next_prefix = next_text[:length]
        if current_suffix.casefold() == next_prefix.casefold():
            return length
    return 0


def trim_overlapping_prefix(current_text: str, next_text: str) -> str:
    """Remove repeated text caused by overlapping realtime transcript chunks."""
    text = next_text.strip()
    if not current_text or not text:
        return text

    character_overlap = _suffix_prefix_overlap_length(current_text, text)
    if character_overlap == len(text):
        return ""
    if character_overlap >= 4 or _contains_cjk_or_fullwidth(text[:character_overlap]):
        return text[character_overlap:].lstrip()

    current_words = _word_spans(current_text)
    next_words = _word_spans(text)
    max_overlap = min(8, len(current_words), len(next_words))
    for word_count in range(max_overlap, 0, -1):
        current_suffix = [word for word, _, _ in current_words[-word_count:]]
        next_prefix = [word for word, _, _ in next_words[:word_count]]
        if current_suffix == next_prefix:
            cut_index = next_words[word_count - 1][2]
            return text[cut_index:].lstrip()

    return text


def normalize_mid_sentence_capitalization(current_text: str, next_text: str) -> str:
    """Lowercase common words that were capitalized only because a chunk started."""
    if not current_text or not next_text:
        return next_text

    current_text = current_text.rstrip()
    if not current_text or current_text[-1] in SENTENCE_ENDINGS:
        return next_text
    if _is_cjk_or_fullwidth(next_text[0]):
        return next_text

    match = WORD_PATTERN.match(next_text)
    if match is None:
        return next_text

    word = match.group(0)
    if word == "I" or not word[0].isupper() or not word[1:].islower():
        return next_text
    if word.casefold() not in MID_SENTENCE_LOWERCASE_STARTS:
        return next_text

    return word[0].lower() + next_text[1:]


def append_transcript_part(current_text: str, next_text: str) -> tuple[str, str]:
    """Append one transcript part and return the new transcript plus printed addition."""
    text = trim_overlapping_prefix(current_text, next_text)
    if not text:
        return current_text, ""

    text = normalize_mid_sentence_capitalization(current_text, text)
    addition = transcript_separator(current_text, text) + text
    return current_text + addition, addition


def join_transcript_parts(parts: list[str]) -> str:
    transcript = ""
    for part in parts:
        transcript, _ = append_transcript_part(transcript, part)
    return transcript


def receive_events(
    connection,
    stop_event: threading.Event,
    completed: list[str],
    display_segments: bool = False,
    debug: bool = False,
) -> None:
    seen_transcripts: set[str] = set()
    continuous_transcript = ""

    def show_transcript(text: str) -> None:
        nonlocal continuous_transcript
        text = text.strip()
        normalized = " ".join(text.split())
        if not normalized or normalized in seen_transcripts:
            return

        updated_transcript, addition = append_transcript_part(continuous_transcript, text)
        if not addition:
            return

        seen_transcripts.add(normalized)
        completed.append(text)
        continuous_transcript = updated_transcript
        print(addition, end="", flush=True)

    try:
        for event in connection:
            event_type = getattr(event, "type", "")
            if debug and event_type not in {
                "conversation.item.input_audio_transcription.delta",
                "conversation.item.input_audio_transcription.completed",
                "conversation.item.input_audio_transcription.segment",
            }:
                print(f"\n[event] {event_type}")
            if event_type == "conversation.item.input_audio_transcription.delta":
                continue
            elif event_type == "conversation.item.input_audio_transcription.segment":
                if display_segments:
                    text = getattr(event, "text", "").strip()
                    show_transcript(text)
            elif event_type == "conversation.item.input_audio_transcription.completed":
                transcript = getattr(event, "transcript", "").strip()
                show_transcript(transcript)
            elif event_type == "conversation.item.input_audio_transcription.failed":
                error = getattr(event, "error", None)
                print(f"\nTranscription failed: {error}", file=sys.stderr)
            elif event_type == "error":
                error = getattr(event, "error", None)
                print(f"\nRealtime error: {error}", file=sys.stderr)
    except Exception as error:
        if not stop_event.is_set():
            print(f"\nRealtime receive failed: {error}", file=sys.stderr)
            stop_event.set()


def audio_sender(
    connection,
    audio_queue: queue.Queue[bytes],
    stop_event: threading.Event,
    resampler: Pcm16MonoResampler,
    gate: NoiseGateState,
    server_vad: bool = False,
    debug: bool = False,
) -> None:
    prefix_buffer: deque[bytes] = deque(maxlen=gate.prefix_frames)
    has_uncommitted_audio = False
    last_debug_at = 0.0

    while not stop_event.is_set():
        try:
            audio_bytes = audio_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        audio_bytes = resampler.process(audio_bytes)
        if not audio_bytes:
            continue

        if server_vad:
            send_audio(connection, audio_bytes)
            has_uncommitted_audio = True
            continue

        if not gate.enabled:
            send_audio(connection, audio_bytes)
            has_uncommitted_audio = True
            gate.speech_frames += 1
            if gate.speech_frames >= gate.max_speech_frames:
                if debug:
                    print("\n[commit] rolling segment")
                commit_buffer(connection)
                has_uncommitted_audio = False
                gate.speech_frames = 0
            continue

        level = rms_level(audio_bytes)
        is_speech = level >= gate.threshold
        now = time.monotonic()
        if debug and now - last_debug_at >= 1.0:
            marker = "speech" if is_speech else "quiet"
            print(f"\n[level] rms={level:.1f} threshold={gate.threshold:.1f} {marker}")
            last_debug_at = now

        if is_speech and not gate.in_speech:
            gate.in_speech = True
            gate.speech_frames = 0
            gate.silent_frames = 0
            for prefix_bytes in prefix_buffer:
                send_audio(connection, prefix_bytes)
            prefix_buffer.clear()

        if gate.in_speech:
            send_audio(connection, audio_bytes)
            has_uncommitted_audio = True
            gate.speech_frames += 1
            gate.silent_frames = 0 if is_speech else gate.silent_frames + 1

            should_commit_for_silence = gate.silent_frames >= gate.silence_frames_to_commit
            should_commit_for_length = gate.speech_frames >= gate.max_speech_frames
            if should_commit_for_silence or should_commit_for_length:
                if has_uncommitted_audio and gate.speech_frames >= gate.min_speech_frames:
                    if debug:
                        print("\n[commit] speech segment")
                    commit_buffer(connection)
                elif has_uncommitted_audio:
                    connection.input_audio_buffer.clear()
                has_uncommitted_audio = False
                gate.in_speech = False
                gate.speech_frames = 0
                gate.silent_frames = 0
        else:
            prefix_buffer.append(audio_bytes)

    if has_uncommitted_audio:
        if debug and not server_vad:
            print("\n[commit] final segment")
        if not server_vad:
            commit_buffer(connection)


def monitor_levels(args: argparse.Namespace) -> int:
    block_seconds = args.block_ms / 1000
    audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=300)
    stop_event = threading.Event()
    signal.signal(signal.SIGINT, lambda signum, frame: stop_event.set())

    device = parse_device(args.device)
    input_sample_rate = get_input_sample_rate(device)
    blocksize = int(input_sample_rate * (args.block_ms / 1000))
    resampler = Pcm16MonoResampler(source_rate=input_sample_rate, target_rate=SAMPLE_RATE)
    callback = audio_callback_factory(audio_queue, stop_event)

    with sd.RawInputStream(
        samplerate=input_sample_rate,
        blocksize=blocksize,
        channels=CHANNELS,
        dtype="int16",
        device=device,
        callback=callback,
    ):
        threshold = args.threshold
        if threshold is None:
            threshold = calibrate_noise(
                audio_queue,
                resampler,
                args.calibrate_seconds,
                block_seconds,
                args.min_threshold,
                args.noise_multiplier,
            )

        print(f"Input sample rate: {input_sample_rate} Hz -> monitoring {SAMPLE_RATE} Hz PCM")
        print("Speak now. Press Ctrl+C to stop.\n")

        started_at = time.monotonic()
        last_print_at = 0.0
        while not stop_event.is_set():
            if args.duration and time.monotonic() - started_at >= args.duration:
                break
            try:
                raw_audio = audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            audio_bytes = resampler.process(raw_audio)
            if not audio_bytes:
                continue
            now = time.monotonic()
            if now - last_print_at < 0.2:
                continue
            level = rms_level(audio_bytes)
            marker = "SPEECH" if level >= threshold else "quiet"
            bar_length = min(50, int(level / 100))
            print(f"RMS {level:7.1f} / threshold {threshold:7.1f} [{marker}] {'#' * bar_length}")
            last_print_at = now

    return 0


def run_realtime_transcription(args: argparse.Namespace) -> int:
    if not get_openai_api_key():
        print("OPENAI_API_KEY is missing or still uses the placeholder value in .env.", file=sys.stderr)
        return 1

    block_seconds = args.block_ms / 1000
    audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=300)
    stop_event = threading.Event()
    completed: list[str] = []

    def request_stop(signum=None, frame=None) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)

    device = parse_device(args.device)
    input_sample_rate = get_input_sample_rate(device)
    blocksize = int(input_sample_rate * (args.block_ms / 1000))
    resampler = Pcm16MonoResampler(source_rate=input_sample_rate, target_rate=SAMPLE_RATE)
    callback = audio_callback_factory(audio_queue, stop_event)
    stream = sd.RawInputStream(
        samplerate=input_sample_rate,
        blocksize=blocksize,
        channels=CHANNELS,
        dtype="int16",
        device=device,
        callback=callback,
    )

    with stream:
        threshold = args.threshold
        if threshold is None and args.local_noise_gate:
            threshold = calibrate_noise(
                audio_queue,
                resampler,
                args.calibrate_seconds,
                block_seconds,
                args.min_threshold,
                args.noise_multiplier,
            )
        elif threshold is None:
            threshold = 0.0

        gate = NoiseGateState(
            threshold=threshold,
            silence_frames_to_commit=ms_to_frames(args.silence_ms, args.block_ms),
            min_speech_frames=ms_to_frames(args.min_utterance_ms, args.block_ms),
            max_speech_frames=max(1, math.ceil(args.max_segment_seconds / block_seconds)),
            prefix_frames=ms_to_frames(args.prefix_ms, args.block_ms),
            enabled=args.local_noise_gate,
        )

        client = OpenAI()
        server_vad = should_use_server_vad(args)
        print(f"Input sample rate: {input_sample_rate} Hz -> streaming {SAMPLE_RATE} Hz PCM")
        print(
            f"Mode: {args.mode}; transcription model: {args.transcription_model}; "
            f"cloud noise reduction: {args.noise_reduction}"
        )
        if args.transcription_model == REALTIME_WHISPER_MODEL and args.prompt:
            print("Prompt note: gpt-realtime-whisper does not support prompts, so the prompt is ignored.")
        print("Connecting to realtime transcription...")
        with client.realtime.connect(extra_query={"intent": "transcription"}) as connection:
            connection.send(build_session_update(args))
            wait_for_session_ready(connection, debug=args.debug)
            drain_audio_queue(audio_queue)
            print("Listening. Speak into the microphone. Press Ctrl+C to stop.\n")

            receiver = threading.Thread(
                target=receive_events,
                args=(
                    connection,
                    stop_event,
                    completed,
                    args.transcription_model == REALTIME_WHISPER_MODEL,
                    args.debug,
                ),
                daemon=True,
            )
            sender = threading.Thread(
                target=audio_sender,
                args=(connection, audio_queue, stop_event, resampler, gate, server_vad, args.debug),
                daemon=True,
            )
            receiver.start()
            sender.start()

            started_at = time.monotonic()
            while not stop_event.is_set():
                if args.duration and time.monotonic() - started_at >= args.duration:
                    stop_event.set()
                    break
                time.sleep(0.05)

            sender.join(timeout=2)
            if args.final_wait_seconds > 0:
                time.sleep(args.final_wait_seconds)
            connection.close()
            receiver.join(timeout=2)

    if completed:
        print()

    if args.output:
        output_path = args.output.expanduser().resolve()
        output_path.write_text(join_transcript_parts(completed), encoding="utf-8")
        print(f"\nSaved transcript to: {output_path}")

    return 0


def main() -> int:
    load_project_environment()
    args = parse_arguments()

    if args.list_devices:
        list_devices()
        return 0
    if args.monitor_levels:
        return monitor_levels(args)

    try:
        return run_realtime_transcription(args)
    except Exception as error:
        print(f"Realtime transcription failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
