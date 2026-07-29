import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from . import __version__
from .config import Settings
from .database import SessionRepository
from .knowledge_graph import KnowledgeGraphStore, KnowledgeGraphUnavailable
from .realtime import ConnectionManager
from .schemas import (
    AnswerSubmittedPayload,
    DemoMessagePayload,
    HealthResponse,
    LocaleChangedPayload,
    QuestionEventPayload,
    QuestionSentPayload,
    RealtimeEnvelope,
    Role,
    SessionCreated,
)

ClientEventRule = tuple[type[BaseModel], set[Role]]

CLIENT_EVENT_RULES: dict[Role, dict[str, ClientEventRule]] = {
    "doctor": {
        "demo.message": (DemoMessagePayload, {"doctor", "patient"}),
        "question.sent": (QuestionSentPayload, {"patient"}),
        "question.cancelled": (QuestionEventPayload, {"patient"}),
        "answer.acknowledged": (QuestionEventPayload, {"patient"}),
    },
    "patient": {
        "demo.message": (DemoMessagePayload, {"doctor", "patient"}),
        "answer.submitted": (AnswerSubmittedPayload, {"doctor"}),
        "explanation.requested": (QuestionEventPayload, {"doctor"}),
        "answer.correction_requested": (QuestionEventPayload, {"doctor"}),
        "locale.changed": (LocaleChangedPayload, {"doctor"}),
    },
}


def _system_event(session_id: str, event_type: str, payload: dict[str, str]) -> RealtimeEnvelope:
    return RealtimeEnvelope(
        event_id=secrets.token_urlsafe(12),
        session_id=session_id,
        source_role="system",
        type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload,
    )


def _static_ready(static_root: Path) -> bool:
    return all((static_root / app / "index.html").is_file() for app in ("doctor", "patient"))


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings()
    repository = SessionRepository(configured.database_path)
    knowledge_graph = KnowledgeGraphStore(configured.knowledge_base_path)
    manager = ConnectionManager()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        repository.initialize()
        yield

    application = FastAPI(
        title="Hering Local API",
        version=__version__,
        lifespan=lifespan,
    )
    application.state.settings = configured
    application.state.repository = repository
    application.state.knowledge_graph = knowledge_graph
    application.state.manager = manager
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(configured.allowed_origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        if not repository.is_ready():
            raise HTTPException(status_code=503, detail="database unavailable")
        return HealthResponse(
            version=__version__,
            database="ready",
            static_assets="ready" if _static_ready(configured.static_root) else "missing",
        )

    @application.post(
        "/api/v1/sessions",
        response_model=SessionCreated,
        status_code=status.HTTP_201_CREATED,
    )
    def create_session() -> SessionCreated:
        created = repository.create_session(configured.session_ttl_minutes)
        return SessionCreated(
            session_id=created.session_id,
            expires_at=created.expires_at,
            doctor_token=created.doctor_token,
            patient_token=created.patient_token,
        )

    @application.get("/api/v1/knowledge-graph")
    def get_knowledge_graph() -> dict[str, Any]:
        try:
            return knowledge_graph.load()
        except KnowledgeGraphUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @application.delete("/api/v1/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_session(session_id: str, role: Role, token: str) -> Response:
        if role != "doctor" or not repository.validate_token(session_id, role, token):
            raise HTTPException(status_code=403, detail="invalid clinician credentials")
        await manager.broadcast(
            session_id,
            _system_event(session_id, "session.ended", {"reason": "ended_by_clinician"}),
        )
        await manager.close_session(session_id)
        if not repository.delete_session(session_id):
            raise HTTPException(status_code=404, detail="session not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.websocket("/ws/v1/sessions/{session_id}")
    async def session_socket(websocket: WebSocket, session_id: str, role: Role, token: str) -> None:
        if not repository.validate_token(session_id, role, token):
            await websocket.close(code=4403, reason="invalid role token")
            return

        await manager.connect(session_id, role, websocket)
        await manager.broadcast(
            session_id, _system_event(session_id, "client.online", {"role": role})
        )
        try:
            while True:
                raw_message = await websocket.receive_json()
                try:
                    incoming = RealtimeEnvelope.model_validate(raw_message)
                except ValidationError:
                    await websocket.close(code=4400, reason="invalid event envelope")
                    return
                if incoming.session_id != session_id or incoming.source_role != role:
                    await websocket.close(code=4403, reason="event role mismatch")
                    return

                normalized = incoming.model_copy(update={"timestamp": datetime.now(UTC)})
                if normalized.type == "heartbeat.ping":
                    await websocket.send_json(
                        _system_event(session_id, "heartbeat.pong", {}).model_dump(mode="json")
                    )
                    continue
                rule = CLIENT_EVENT_RULES[role].get(normalized.type)
                if rule is None:
                    await websocket.close(code=4403, reason="event type not allowed for role")
                    return
                payload_model, target_roles = rule
                try:
                    validated_payload = payload_model.model_validate(normalized.payload)
                except ValidationError:
                    await websocket.close(code=4400, reason="invalid event payload")
                    return

                normalized = normalized.model_copy(
                    update={"payload": validated_payload.model_dump(mode="json", exclude_none=True)}
                )
                if not repository.record_event(normalized):
                    continue
                await manager.send_to_roles(session_id, target_roles, normalized)
                if normalized.type == "answer.submitted":
                    question_id = str(normalized.payload["question_id"])
                    await websocket.send_json(
                        _system_event(
                            session_id,
                            "answer.received",
                            {"question_id": question_id},
                        ).model_dump(mode="json")
                    )
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(session_id, role, websocket)
            await manager.broadcast(
                session_id, _system_event(session_id, "client.offline", {"role": role})
            )

    if (configured.static_root / "doctor" / "index.html").is_file():
        application.mount(
            "/doctor",
            StaticFiles(directory=configured.static_root / "doctor", html=True),
            name="doctor",
        )
    if (configured.static_root / "patient" / "index.html").is_file():
        application.mount(
            "/patient",
            StaticFiles(directory=configured.static_root / "patient", html=True),
            name="patient",
        )
    return application


app = create_app()
