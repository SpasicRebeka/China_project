"""Process doctor text for patient-friendly display."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config import get_openai_api_key, load_project_environment
from medical_language import MedicalLanguageProcessor


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate medical text to English and simplify it for patient display."
    )
    parser.add_argument("text", nargs="?", help="Text to process. If omitted, use --file or stdin.")
    parser.add_argument("--file", "-f", type=Path, help="Read the text from this UTF-8 file.")
    parser.add_argument(
        "--source-language",
        default="auto",
        help="Language of the input text, or 'auto'. Defaults to auto.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Where to save the structured JSON result.",
    )
    parser.add_argument(
        "--patient-output",
        type=Path,
        help="Where to save only the patient-friendly text.",
    )
    return parser.parse_args()


def read_input_text(args: argparse.Namespace) -> str:
    if args.file and args.text:
        raise ValueError("Use either positional text or --file, not both.")
    if args.file:
        return args.file.expanduser().resolve().read_text(encoding="utf-8").strip()
    if args.text:
        return args.text.strip()
    if sys.stdin.isatty():
        raise ValueError("Provide text, use --file, or pipe text through stdin.")
    return sys.stdin.read().strip()


def main() -> int:
    load_project_environment()
    args = parse_arguments()

    if not get_openai_api_key():
        print("OPENAI_API_KEY is missing or still uses the placeholder value in .env.", file=sys.stderr)
        return 1

    try:
        input_text = read_input_text(args)
        if not input_text:
            raise ValueError("Input text is empty.")

        processor = MedicalLanguageProcessor()
        result = processor.process(input_text, source_language=args.source_language)
    except Exception as error:
        print(f"Medical language processing failed: {error}", file=sys.stderr)
        return 1

    result_json = json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
    if args.output:
        output_path = args.output.expanduser().resolve()
        output_path.write_text(result_json, encoding="utf-8")
        print(f"Saved structured result to: {output_path}")

    if args.patient_output:
        patient_path = args.patient_output.expanduser().resolve()
        patient_path.write_text(result.patient_friendly_text, encoding="utf-8")
        print(f"Saved patient text to: {patient_path}")

    print("\nPatient-friendly text:\n")
    print(result.patient_friendly_text)

    if result.simple_terms:
        print("\nSimple terms:")
        for term in result.simple_terms:
            print(f"- {term.term}: {term.plain_language}")

    if result.critical_items_to_confirm:
        print("\nDoctor should confirm:")
        for item in result.critical_items_to_confirm:
            print(f"- {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
