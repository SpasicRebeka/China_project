"""Cloud language processing for accessible hospital communication."""

from __future__ import annotations

import json
import re
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from config import PROJECT_ROOT, get_text_model


DEFAULT_GLOSSARY_PATH = PROJECT_ROOT / "data" / "medical_glossary.json"


class GlossaryEntry(BaseModel):
    """One reviewed medical term from the local glossary database."""

    model_config = ConfigDict(extra="forbid")

    term: str
    plain_language: str
    aliases: list[str] = Field(default_factory=list)


class SimpleTerm(BaseModel):
    """A medical term and its patient-friendly explanation."""

    model_config = ConfigDict(extra="forbid")

    term: str = Field(description="The professional or medical term.")
    plain_language: str = Field(description="A simple explanation of the term.")


class MedicalLanguageResult(BaseModel):
    """Structured result for the patient display and doctor review screen."""

    model_config = ConfigDict(extra="forbid")

    original_text: str = Field(description="The original input text.")
    detected_source_language: str = Field(description="The detected language of the original text.")
    english_translation: str = Field(description="The English translation, preserving numbers and names.")
    patient_friendly_text: str = Field(description="Simple English suitable for patient display.")
    simple_terms: list[SimpleTerm] = Field(description="Important medical terms explained simply.")
    critical_items_to_confirm: list[str] = Field(
        description="Medication names, doses, dates, measurements, allergies, or instructions that need confirmation."
    )
    safety_notes: list[str] = Field(description="Short safety notes for the interface.")
    requires_doctor_confirmation: bool = Field(description="Always true for clinical communication.")


def load_glossary(glossary_path: Path = DEFAULT_GLOSSARY_PATH) -> list[GlossaryEntry]:
    """Load the reviewed glossary entries used as local RAG context."""
    with glossary_path.open("r", encoding="utf-8") as file_handle:
        raw_entries = json.load(file_handle)
    return [GlossaryEntry.model_validate(entry) for entry in raw_entries]


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)"
    return re.search(pattern, text.lower()) is not None


def retrieve_glossary_terms(
    text: str,
    glossary: list[GlossaryEntry] | None = None,
    max_terms: int = 12,
) -> list[SimpleTerm]:
    """Find glossary entries mentioned in the text.

    This is the prototype's RAG retrieval step. In production, this can be
    replaced by vector search or a licensed medical terminology database.
    """
    entries = glossary or load_glossary()
    matches: list[SimpleTerm] = []
    seen_terms: set[str] = set()

    for entry in entries:
        candidates = [entry.term, *entry.aliases]
        if any(_contains_phrase(text, candidate) for candidate in candidates):
            normalized = entry.term.lower()
            if normalized not in seen_terms:
                matches.append(SimpleTerm(term=entry.term, plain_language=entry.plain_language))
                seen_terms.add(normalized)
        if len(matches) >= max_terms:
            break

    return matches


class MedicalLanguageProcessor:
    """Translate medical text to English, retrieve term context, and simplify it."""

    def __init__(
        self,
        model: str | None = None,
        glossary_path: Path = DEFAULT_GLOSSARY_PATH,
        client: OpenAI | None = None,
    ) -> None:
        self.model = model or get_text_model()
        self.glossary = load_glossary(glossary_path)
        self.client = client or OpenAI()

    def translate_to_english(self, text: str, source_language: str = "auto") -> str:
        """Translate source text to English before simplification."""
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "You translate hospital communication into clear English. "
                "If the text is already English, keep it in English and only fix obvious speech-to-text noise. "
                "Preserve medication names, numbers, units, dates, times, allergies, and body parts exactly. "
                "Do not add diagnosis, treatment advice, or new facts. Return only the translated English text."
            ),
            input=f"Source language: {source_language}\n\nText:\n{text}",
        )
        return response.output_text.strip()

    def simplify_for_patient(
        self,
        original_text: str,
        english_translation: str,
        source_language: str = "auto",
    ) -> MedicalLanguageResult:
        """Create a patient-friendly explanation with glossary context."""
        glossary_terms = retrieve_glossary_terms(english_translation, self.glossary)
        glossary_context = "\n".join(
            f"- {term.term}: {term.plain_language}" for term in glossary_terms
        ) or "- No local glossary terms matched."

        response = self.client.responses.parse(
            model=self.model,
            text_format=MedicalLanguageResult,
            instructions=(
                "You are the cloud language layer for an accessible hospital communication device. "
                "Your job is communication support only. Do not diagnose, recommend treatment, change doses, "
                "or decide what the patient should do. Make professional medical language easier to understand. "
                "Use short sentences and common words. Preserve all medication names, measurements, numbers, "
                "dates, times, and follow-up instructions. If something sounds clinically important, place it "
                "in critical_items_to_confirm. The output must be reviewed by a healthcare professional."
            ),
            input=(
                f"Source language setting: {source_language}\n\n"
                f"Original text:\n{original_text}\n\n"
                f"English translation:\n{english_translation}\n\n"
                f"Local glossary context:\n{glossary_context}\n\n"
                "Return the structured result for the touchscreen patient display."
            ),
        )

        result = response.output_parsed
        if result is None:
            raise RuntimeError("The model did not return a parsed medical language result.")

        merged_terms = _merge_terms(result.simple_terms, glossary_terms)
        return result.model_copy(
            update={
                "original_text": original_text,
                "english_translation": english_translation,
                "simple_terms": merged_terms,
                "requires_doctor_confirmation": True,
            }
        )

    def process(self, text: str, source_language: str = "auto") -> MedicalLanguageResult:
        """Run the full translate -> retrieve -> simplify cloud pipeline."""
        english_translation = self.translate_to_english(text, source_language=source_language)
        return self.simplify_for_patient(
            original_text=text,
            english_translation=english_translation,
            source_language=source_language,
        )


def _merge_terms(
    model_terms: list[SimpleTerm],
    glossary_terms: list[SimpleTerm],
) -> list[SimpleTerm]:
    merged: list[SimpleTerm] = []
    seen: set[str] = set()

    for term in [*glossary_terms, *model_terms]:
        normalized = term.term.strip().lower()
        if normalized and normalized not in seen:
            merged.append(term)
            seen.add(normalized)

    return merged
