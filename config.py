"""Shared configuration helpers for the prototype."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent

def load_project_environment() -> None:
    """Load local environment variables without requiring a shell-specific setup."""
    env_file = PROJECT_ROOT / ".env"
    legacy_env_file = PROJECT_ROOT / "env"

    load_dotenv(env_file)

    # Some early local versions used a file named "env". Keep supporting it, but
    # only when ".env" is missing or still contains the example placeholder.
    if not get_openai_api_key() and legacy_env_file.is_file():
        load_dotenv(legacy_env_file, override=True)


def get_openai_api_key() -> str | None:
    """Return a usable OpenAI API key, ignoring example placeholder values."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    normalized_key = key.lower()

    return key


def get_text_model() -> str:
    """Return the OpenAI text model used for translation and simplification."""
    return os.environ.get("LANGUAGE_MODEL", "gpt-5.6-luna")


def get_transcription_model() -> str:
    """Return the OpenAI audio transcription model."""
    return os.environ.get("TRANSCRIPTION_MODEL", "gpt-4o-transcribe")


def get_realtime_transcription_model() -> str:
    """Return the low-latency realtime transcription model."""
    return os.environ.get("REALTIME_TRANSCRIPTION_MODEL", "gpt-realtime-whisper")


def get_realtime_transcription_delay() -> str:
    """Return the realtime transcription latency/accuracy tradeoff."""
    return os.environ.get("REALTIME_TRANSCRIPTION_DELAY", "minimal")


def get_language_reasoning_effort() -> str | None:
    """Return the reasoning effort for low-latency language processing."""
    effort = os.environ.get("LANGUAGE_REASONING_EFFORT", "none").strip().lower()
    return effort or None
