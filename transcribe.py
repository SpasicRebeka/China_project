"""Transcribe one local audio file with the OpenAI transcription API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openai import OpenAI

from config import get_openai_api_key, get_transcription_model, load_project_environment
from medical_language import MedicalLanguageProcessor


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
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Also translate and simplify the transcript for patient display.",
    )
    parser.add_argument(
        "--source-language",
        default="auto",
        help="Language of the doctor's speech, or 'auto'. Used with --explain.",
    )
    parser.add_argument(
        "--explanation-output",
        type=Path,
        help="Where to save the structured explanation JSON. Defaults to .patient.json next to the audio.",
    )
    return parser.parse_args()


def transcribe(audio_file: Path, model: str) -> str:
    """Upload one audio file and return its speech-to-text transcript."""
    client = OpenAI()
    with audio_file.open("rb") as file_handle:
        result = client.audio.transcriptions.create(model=model, file=file_handle)
    return result.text


def main() -> int:
    load_project_environment()
    args = parse_arguments()
    audio_file = args.audio_file.expanduser().resolve()

    if not audio_file.is_file():
        print(f"Audio file not found: {audio_file}", file=sys.stderr)
        return 1
    if not get_openai_api_key():
        print("OPENAI_API_KEY is missing or still uses the placeholder value in .env.", file=sys.stderr)
        return 1

    output_file = (args.output or audio_file.with_suffix(".txt")).expanduser().resolve()
    model = get_transcription_model()

    try:
        transcript = transcribe(audio_file, model)
        explanation = None
        if args.explain:
            processor = MedicalLanguageProcessor()
            explanation = processor.process(transcript, source_language=args.source_language)
    except Exception as error:
        print(f"Transcription failed: {error}", file=sys.stderr)
        return 1

    output_file.write_text(transcript, encoding="utf-8")
    print("\nTranscript:\n")
    print(transcript)
    print(f"\nSaved to: {output_file}")

    if explanation:
        explanation_file = (
            args.explanation_output or audio_file.with_suffix(".patient.json")
        ).expanduser().resolve()
        explanation_file.write_text(
            json.dumps(explanation.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("\nPatient-friendly text:\n")
        print(explanation.patient_friendly_text)
        print(f"\nSaved explanation to: {explanation_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
