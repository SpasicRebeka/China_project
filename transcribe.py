"""Transcribe one local audio file with the OpenAI transcription API."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def parse_arguments() -> argparse.Namespace:
    """Read the audio-file path and optional output path from the command line."""
    parser = argparse.ArgumentParser(
        description="Convert a local audio file into text using OpenAI transcription."
    )
    parser.add_argument("audio_file", type=Path, help="Path to the audio file to transcribe.")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Where to save the transcript. Defaults to the audio file name with a .txt suffix.",
    )
    return parser.parse_args()


def transcribe(audio_file: Path, model: str) -> str:
    """Upload one audio file and return its speech-to-text transcript."""
    client = OpenAI()
    with audio_file.open("rb") as file_handle:
        result = client.audio.transcriptions.create(model=model, file=file_handle)
    return result.text


def main() -> int:
    # Always load the project's .env file, even when this command is launched
    # from a different folder (for example while targeting a file in Downloads).
    load_dotenv(Path(__file__).with_name(".env"))
    args = parse_arguments()
    audio_file = args.audio_file.expanduser().resolve()

    if not audio_file.is_file():
        print(f"Audio file not found: {audio_file}", file=sys.stderr)
        return 1
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is missing. Copy .env.example to .env and add your key.", file=sys.stderr)
        return 1

    output_file = (args.output or audio_file.with_suffix(".txt")).expanduser().resolve()
    model = os.environ.get("TRANSCRIPTION_MODEL", "gpt-4o-transcribe")

    try:
        transcript = transcribe(audio_file, model)
    except Exception as error:
        print(f"Transcription failed: {error}", file=sys.stderr)
        return 1

    output_file.write_text(transcript, encoding="utf-8")
    print("\nTranscript:\n")
    print(transcript)
    print(f"\nSaved to: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
