from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["doctor", "patient"]
SourceRole = Literal["doctor", "patient", "system"]
PatientLocale = Literal["zh-CN", "en-US"]
ClinicalAnswerType = Literal[
    "single_choice",
    "multi_choice",
    "number",
    "duration",
    "date_or_relative",
    "free_text",
]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    database: Literal["ready"]
    static_assets: Literal["ready", "missing"]


class SessionCreated(BaseModel):
    session_id: str
    expires_at: datetime
    doctor_token: str
    patient_token: str


class RealtimeEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=8, max_length=128)
    session_id: str = Field(min_length=8, max_length=128)
    source_role: SourceRole
    type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class LocalizedClinicalText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zh: str = Field(min_length=1, max_length=500)
    en: str = Field(min_length=1, max_length=500)


class ClinicalAnswerOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=128)
    label: LocalizedClinicalText


class QuestionSentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=128)
    field: str = Field(min_length=1, max_length=128)
    prompt: LocalizedClinicalText
    answer_type: ClinicalAnswerType
    options: list[ClinicalAnswerOption] = Field(default_factory=list, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    knowledge_version: str = Field(min_length=1, max_length=64)
    source_refs: list[str] = Field(default_factory=list, max_length=32)


class AnswerSubmittedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=128)
    answer_type: ClinicalAnswerType
    structured_value: Any
    display_text: str = Field(min_length=1, max_length=1000)
    answer_state: Literal["answered", "skipped"]
    patient_language: PatientLocale


class QuestionEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=128)


class LocaleChangedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locale: PatientLocale


class DemoMessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=256)


class TranscriptSegment(BaseModel):
    segment_id: str
    text: str
    is_final: bool
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    language: str
    started_at_ms: int = Field(ge=0)
    ended_at_ms: int | None = Field(default=None, ge=0)
