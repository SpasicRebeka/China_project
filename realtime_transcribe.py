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
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent

import sounddevice as sd
from openai import OpenAI

from config import (
    get_openai_api_key,
    get_language_reasoning_effort,
    get_realtime_transcription_delay,
    get_realtime_transcription_model,
    get_text_model,
    load_project_environment,
)


SAMPLE_RATE = 24_000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2
REALTIME_WHISPER_MODEL = "gpt-realtime-whisper"
DEFAULT_SIMPLIFICATION_INSTRUCTIONS = dedent(
    """\
    Prepare temporally arriving doctor-speech transcript chunks for a patient display. The result must
    be accurate, easy for an everyday patient to understand, and as close to the doctor's original
    wording as possible. Follow these rules in priority order:

    1. Simplify genuinely difficult or moderately difficult medical language. Replace medical or
    clinical terms, diagnoses, procedures, anatomy, tests, and technical symptom names with direct
    everyday wording without losing their meaning. Do not merely repeat the technical term in
    parentheses. English examples: 'tachycardia' -> 'a heart rate that is too fast'; 'intravenous
    injection' -> 'giving medicine through a needle into a vein'; 'myocardial infarction' -> 'a heart
    attack caused by a blocked blood vessel damaging the heart muscle'. Chinese examples: '心动过速'
    -> '心跳过快'; '静脉注射' -> '通过静脉打针给药'; '心肌梗死' ->
    '心脏血管突然堵住，造成心肌受损'.

    2. Preserve ordinary language. Do not paraphrase, polish, shorten, or replace words that an everyday
    person can already understand. Preserve the speaker's degree of certainty and time wording. English
    examples: keep 'Take one tablet every morning' unchanged; keep 'This may help over the long term'
    unchanged, including 'may' and 'long term'. Chinese examples: keep '每天早上吃一片' unchanged; keep
    '这可能对你以后有帮助' unchanged, including '可能'.

    3. Repair chunk boundaries and presentation only when that makes temporally arriving speech
    understandable. Join fragments that clearly form one thought; remove only accidental overlap or
    immediate repetition caused by chunking; and correct capitalization, commas, periods, question
    marks, exclamation marks, and obvious sentence boundaries. You may add a minimal connecting word
    only when the intended connection is unambiguous. Do not reorder ideas, omit facts, summarize, or
    rewrite for style. English example: 'the pain started / yesterday and it / gets worse when you walk
    do you feel dizzy' -> 'The pain started yesterday, and it gets worse when you walk. Do you feel
    dizzy?' Chinese example: '这个药每天吃两次 / 每天吃两次你对青霉素过敏吗' ->
    '这个药每天吃两次。你对青霉素过敏吗？'

    4. Actively correct obvious speech-recognition errors. When a recognized word or short phrase is
    clearly unnatural, nonsensical, or from the wrong context, and therefore does not fit the surrounding
    sentence or medical discussion, do not preserve it literally. Replace it naturally with the most
    probable intended word or phrase, using its sound, the sentence grammar, the nearby words, and the
    current medical topic as evidence. An obviously out-of-context word should be corrected even when
    the transcript does not explicitly mark it as uncertain. Make the smallest possible correction and
    leave the rest of the sentence unchanged. English example in a blood-pressure discussion: 'Your
    blood pleasure is high' -> 'Your blood pressure is high'. Chinese example in a measurement
    discussion: '请测量血鸭' -> '请测量血压'. If two or more replacements remain reasonably plausible,
    retain the recognized wording rather than choosing arbitrarily. Never use a correction to invent a
    diagnosis, medicine, dose, number, instruction, or missing fact.

    Always preserve medicine names, doses, numbers, units, dates, times, allergies, measurements,
    negation, uncertainty, and follow-up instructions exactly unless rule 4 identifies an unambiguous
    recognition error. Do not add medical advice, diagnosis, explanation, reassurance, or facts that the
    doctor did not say. If the transcript is incomplete, process only the clear part and do not complete
    the thought. Return only the patient-facing text in the requested output language, with no notes,
    labels, alternatives, or explanation of your edits.
    """
).strip()
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
class SimplificationState:
    """Finalized transcript chunks waiting for patient-friendly simplification."""

    completed: list[str] = field(default_factory=list)
    simplified: list[str] = field(default_factory=list)
    patient_heading_printed: bool = False
    speech_active: bool = False
    last_speech_stopped_at: float | None = None
    simplified_until_count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


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
        default=None,
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
        "--simplified-output",
        type=Path,
        help="Save patient-friendly simplified text to this UTF-8 file.",
    )
    parser.add_argument(
        "--simplify-live",
        dest="simplify_live",
        action="store_true",
        help="Call OpenAI to simplify finalized transcript text after longer pauses.",
    )
    parser.add_argument(
        "--no-simplify-live",
        dest="simplify_live",
        action="store_false",
        help="Only show the direct realtime transcript.",
    )
    parser.add_argument(
        "--simplify-pause-seconds",
        type=float,
        default=1.3,
        help="Doctor pause duration before the simplification API call runs.",
    )
    parser.add_argument(
        "--simplify-min-chars",
        type=int,
        default=12,
        help="Minimum new finalized characters needed before simplification runs.",
    )
    parser.add_argument(
        "--simplified-language",
        default="same",
        help="Output language for simplified text: same, en, zh, or another language name/code.",
    )
    parser.add_argument(
        "--delay",
        choices=["minimal", "low", "medium", "high", "xhigh"],
        default=get_realtime_transcription_delay(),
        help="Realtime transcription delay. Minimal is fastest; higher can improve accuracy.",
    )
    parser.add_argument(
        "--vad-threshold",
        type=float,
        default=0.35,
        help="Server VAD threshold for quiet-room mode. Lower is more sensitive.",
    )
    parser.add_argument(
        "--silence-ms",
        type=int,
        default=200,
        help="Silence duration before committing one speech segment.",
    )
    parser.add_argument(
        "--prefix-ms",
        type=int,
        default=200,
        help="Audio kept before speech starts so first words are not clipped.",
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
    parser.set_defaults(simplify_live=True)
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


def build_session_update(args: argparse.Namespace) -> dict:
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
                    "noise_reduction": {"type": "near_field"},
                    "transcription": transcription,
                    "turn_detection": turn_detection,
                }
            },
        },
    }


def should_use_server_vad(args: argparse.Namespace) -> bool:
    return args.mode == "quiet-room" and args.transcription_model != REALTIME_WHISPER_MODEL


def audio_callback_factory(
    audio_queue: queue.Queue[bytes],
    stop_event: threading.Event,
    audio_warning_event: threading.Event,
):
    def callback(indata, frames, time_info, status) -> None:
        if status:
            # PortAudio invokes this on its real-time callback thread. Printing or
            # doing other blocking work here can itself cause further overflows.
            audio_warning_event.set()
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


def build_reasoning_config() -> dict[str, str] | None:
    effort = get_language_reasoning_effort()
    if not effort:
        return None
    return {"effort": effort}


def describe_patient_output_language(source_language: str, target_language: str) -> str:
    normalized = target_language.strip().lower()
    if normalized in {"", "same", "source"}:
        return f"Use the same language as the doctor transcript. Source language setting: {source_language}."
    if normalized in {"zh", "cn", "chinese", "mandarin"}:
        return "Chinese"
    if normalized in {"en", "english"}:
        return "English"
    return target_language


def simplify_clinical_text(
    client: OpenAI,
    text: str,
    source_language: str,
    target_language: str,
    model: str,
    reasoning: dict[str, str] | None,
) -> str:
    """Call OpenAI directly to simplify finalized doctor speech for the patient."""
    request = {
        "model": model,
        "max_output_tokens": 500,
        "instructions": DEFAULT_SIMPLIFICATION_INSTRUCTIONS,
        "input": (
            f"Source language setting: {source_language}\n\n"
            "Patient output language: "
            f"{describe_patient_output_language(source_language, target_language)}\n\n"
            f"Doctor transcript:\n{text}\n\n"
            "Simplify this for the patient display."
        ),
    }
    if reasoning:
        request["reasoning"] = reasoning

    response = client.responses.create(**request)
    return response.output_text.strip()


def simplify_after_pause_worker(
    args: argparse.Namespace,
    state: SimplificationState,
    stop_event: threading.Event,
    debug: bool = False,
) -> None:
    client: OpenAI | None = None
    model = get_text_model()
    reasoning = build_reasoning_config()

    while not stop_event.is_set():
        time.sleep(0.2)
        now = time.monotonic()

        with state.lock:
            if state.speech_active or state.last_speech_stopped_at is None:
                continue
            quiet_for = now - state.last_speech_stopped_at
            if quiet_for < args.simplify_pause_seconds:
                continue

            end_count = len(state.completed)
            pending_parts = state.completed[state.simplified_until_count:end_count]
            pending_text = join_transcript_parts(pending_parts).strip()
            if len(pending_text) < args.simplify_min_chars:
                continue

            state.simplified_until_count = end_count

        if client is None:
            client = OpenAI()

        try:
            simplified_text = simplify_clinical_text(
                client=client,
                text=pending_text,
                source_language=args.language,
                target_language=args.simplified_language,
                model=model,
                reasoning=reasoning,
            )
        except Exception as error:
            print(f"\n\nSimplification failed: {error}\n", file=sys.stderr)
            if debug:
                print(f"[simplify input] {pending_text}", file=sys.stderr)
            continue

        if simplified_text:
            with state.lock:
                should_print_heading = not state.patient_heading_printed
                state.patient_heading_printed = True
                state.simplified.append(simplified_text)
            if should_print_heading:
                print(f"\n\nPatient simplified text:\n{simplified_text}", flush=True)
            else:
                print(simplified_text, flush=True)


def receive_events(
    connection,
    stop_event: threading.Event,
    state: SimplificationState,
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
        with state.lock:
            state.completed.append(text)
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
            elif event_type == "input_audio_buffer.speech_started":
                with state.lock:
                    state.speech_active = True
                    state.last_speech_stopped_at = None
            elif event_type == "input_audio_buffer.speech_stopped":
                with state.lock:
                    state.speech_active = False
                    state.last_speech_stopped_at = time.monotonic()
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
    max_segment_frames: int,
    server_vad: bool = False,
    debug: bool = False,
) -> None:
    has_uncommitted_audio = False
    frames_since_commit = 0

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

        send_audio(connection, audio_bytes)
        has_uncommitted_audio = True
        frames_since_commit += 1
        if frames_since_commit >= max_segment_frames:
            if debug:
                print("\n[commit] timed segment")
            commit_buffer(connection)
            has_uncommitted_audio = False
            frames_since_commit = 0

    if has_uncommitted_audio:
        if debug and not server_vad:
            print("\n[commit] final segment")
        if not server_vad:
            commit_buffer(connection)


def run_realtime_transcription(args: argparse.Namespace) -> int:
    if not get_openai_api_key():
        print("OPENAI_API_KEY is missing or still uses the placeholder value in .env.", file=sys.stderr)
        return 1

    block_seconds = args.block_ms / 1000
    audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=300)
    stop_event = threading.Event()
    simplifier_stop_event = threading.Event()
    audio_warning_event = threading.Event()
    simplification_state = SimplificationState()

    def request_stop(signum=None, frame=None) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)

    device = parse_device(args.device)
    input_sample_rate = get_input_sample_rate(device)
    blocksize = int(input_sample_rate * (args.block_ms / 1000))
    resampler = Pcm16MonoResampler(source_rate=input_sample_rate, target_rate=SAMPLE_RATE)
    callback = audio_callback_factory(audio_queue, stop_event, audio_warning_event)
    stream = sd.RawInputStream(
        samplerate=input_sample_rate,
        blocksize=blocksize,
        channels=CHANNELS,
        dtype="int16",
        device=device,
        callback=callback,
    )

    max_segment_frames = max(1, math.ceil(args.max_segment_seconds / block_seconds))

    client = OpenAI()
    server_vad = should_use_server_vad(args)
    print(f"Input sample rate: {input_sample_rate} Hz -> streaming {SAMPLE_RATE} Hz PCM")
    print(
        f"Mode: {args.mode}; transcription model: {args.transcription_model}; "
        "cloud noise reduction: near_field"
    )
    if args.transcription_model == REALTIME_WHISPER_MODEL and args.prompt:
        print("Prompt note: gpt-realtime-whisper does not support prompts, so the prompt is ignored.")
    print("Connecting to realtime transcription...")
    with client.realtime.connect(extra_query={"intent": "transcription"}) as connection:
        connection.send(build_session_update(args))
        wait_for_session_ready(connection, debug=args.debug)
        print("Listening. Speak into the microphone. Press Ctrl+C to stop.\n")
        simplify_after_vad_pause = args.simplify_live and server_vad
        if simplify_after_vad_pause:
            print(
                "Patient simplification is enabled. "
                f"It updates {args.simplify_pause_seconds:.1f}s after OpenAI detects speech has stopped.\n"
            )
        elif args.simplify_live:
            print(
                "Patient simplification is disabled because this model/mode does not provide server speech-stop events.\n"
            )

        simplifier = None
        if simplify_after_vad_pause:
            simplifier = threading.Thread(
                target=simplify_after_pause_worker,
                args=(args, simplification_state, simplifier_stop_event, args.debug),
                daemon=True,
            )
            simplifier.start()

        receiver = threading.Thread(
            target=receive_events,
            args=(
                connection,
                stop_event,
                simplification_state,
                args.transcription_model == REALTIME_WHISPER_MODEL,
                args.debug,
            ),
            daemon=True,
        )
        sender = threading.Thread(
            target=audio_sender,
            args=(connection, audio_queue, stop_event, resampler, max_segment_frames, server_vad, args.debug),
            daemon=True,
        )
        receiver.start()
        sender.start()

        # Start capture only after the remote session and worker threads are
        # ready. This avoids accumulating/loss of audio during TLS/WebSocket
        # setup, which commonly produces startup overflows on Raspberry Pi.
        with stream:
            started_at = time.monotonic()
            last_audio_warning_at = 0.0
            while not stop_event.is_set():
                now = time.monotonic()
                if args.duration and now - started_at >= args.duration:
                    stop_event.set()
                    break
                if audio_warning_event.is_set():
                    audio_warning_event.clear()
                    if now - last_audio_warning_at >= 5.0:
                        print(
                            "\nAudio warning: microphone input overflow; some audio was dropped. "
                            "Try a larger --block-ms value (for example 50).",
                            file=sys.stderr,
                        )
                        last_audio_warning_at = now
                time.sleep(0.05)

        sender.join(timeout=2)
        if args.final_wait_seconds > 0:
            time.sleep(args.final_wait_seconds)
        connection.close()
        receiver.join(timeout=2)
        simplifier_stop_event.set()
        if simplifier:
            simplifier.join(timeout=2)

    with simplification_state.lock:
        completed = list(simplification_state.completed)
        simplified = list(simplification_state.simplified)

    if completed:
        print()

    if args.output:
        output_path = args.output.expanduser().resolve()
        output_path.write_text(join_transcript_parts(completed), encoding="utf-8")
        print(f"\nSaved transcript to: {output_path}")

    if args.simplified_output:
        simplified_path = args.simplified_output.expanduser().resolve()
        simplified_path.write_text(join_transcript_parts(simplified), encoding="utf-8")
        print(f"\nSaved simplified text to: {simplified_path}")

    return 0


def main() -> int:
    load_project_environment()
    args = parse_arguments()

    if args.list_devices:
        list_devices()
        return 0

    try:
        return run_realtime_transcription(args)
    except Exception as error:
        print(f"Realtime transcription failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
