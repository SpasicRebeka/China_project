from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.database import SessionRepository
from app.main import create_app


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "test.db",
        static_root=tmp_path / "static",
        session_ttl_minutes=10,
    )


def create_session(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/v1/sessions")
    assert response.status_code == 201
    return response.json()


def event(
    session: dict[str, Any],
    role: str,
    event_type: str = "demo.message",
    payload: dict[str, Any] | None = None,
    event_id: str = "test-event-0001",
) -> dict[str, Any]:
    return {
        "version": "1.0",
        "event_id": event_id,
        "session_id": session["session_id"],
        "source_role": role,
        "type": event_type,
        "timestamp": "2026-07-24T12:00:00Z",
        "payload": payload or {"text": "hello"},
    }


def receive_until(socket: Any, event_type: str) -> dict[str, Any]:
    for _ in range(5):
        message = socket.receive_json()
        if message["type"] == event_type:
            return message
    raise AssertionError(f"event {event_type!r} was not received")


def test_health_and_session_creation(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for(tmp_path))) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json() == {
            "status": "ok",
            "version": "0.1.0",
            "database": "ready",
            "static_assets": "missing",
        }

        session = create_session(client)
        assert session["doctor_token"] != session["patient_token"]
        assert len(session["session_id"]) >= 8


def test_knowledge_graph_uses_versioned_repository_source(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for(tmp_path))) as client:
        response = client.get("/api/v1/knowledge-graph")

    assert response.status_code == 200
    graph = response.json()
    assert graph["kb_version"] == "0.1.0"
    assert len(graph["symptoms"]) == 7
    chest_tightness = next(
        symptom for symptom in graph["symptoms"] if symptom["id"] == "chest_tightness"
    )
    assert chest_tightness["questions"][0]["prompt"]["zh"] == "胸闷最像哪一种感觉？"


def test_knowledge_graph_reports_unavailable_source(tmp_path: Path) -> None:
    configured = settings_for(tmp_path).model_copy(
        update={"knowledge_base_path": tmp_path / "missing-knowledge-base.json"}
    )
    with TestClient(create_app(configured)) as client:
        response = client.get("/api/v1/knowledge-graph")

    assert response.status_code == 503
    assert response.json()["detail"] == "knowledge graph file is unavailable"


def test_role_tokens_and_realtime_relay(tmp_path: Path) -> None:
    configured = settings_for(tmp_path)
    with TestClient(create_app(configured)) as client:
        session = create_session(client)
        doctor_url = (
            f"/ws/v1/sessions/{session['session_id']}"
            f"?role=doctor&token={session['doctor_token']}"
        )
        patient_url = (
            f"/ws/v1/sessions/{session['session_id']}"
            f"?role=patient&token={session['patient_token']}"
        )
        with client.websocket_connect(doctor_url) as doctor:
            receive_until(doctor, "client.online")
            with client.websocket_connect(patient_url) as patient:
                receive_until(patient, "client.online")
                doctor.send_json(event(session, "doctor"))
                relayed = receive_until(patient, "demo.message")
                assert relayed["payload"] == {"text": "hello"}

        repository = SessionRepository(configured.database_path)
        assert repository.event_count(session["session_id"]) == 1


def test_invalid_role_token_is_rejected(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for(tmp_path))) as client:
        session = create_session(client)
        url = f"/ws/v1/sessions/{session['session_id']}?role=patient&token=wrong"
        with pytest.raises(WebSocketDisconnect) as rejected, client.websocket_connect(url):
            pass
        assert rejected.value.code == 4403


def test_clinical_events_are_validated_and_relayed_by_role(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for(tmp_path))) as client:
        session = create_session(client)
        doctor_url = (
            f"/ws/v1/sessions/{session['session_id']}"
            f"?role=doctor&token={session['doctor_token']}"
        )
        patient_url = (
            f"/ws/v1/sessions/{session['session_id']}"
            f"?role=patient&token={session['patient_token']}"
        )
        question = {
            "question_id": "question-1",
            "field": "severity",
            "prompt": {"zh": "您现在的症状有多严重？", "en": "How severe is it?"},
            "answer_type": "single_choice",
            "options": [
                {"code": "mild", "label": {"zh": "轻度", "en": "Mild"}},
                {"code": "severe", "label": {"zh": "重度", "en": "Severe"}},
            ],
            "knowledge_version": "test",
            "source_refs": ["test"],
        }
        answer = {
            "question_id": "question-1",
            "answer_type": "single_choice",
            "structured_value": "mild",
            "display_text": "轻度",
            "answer_state": "answered",
            "patient_language": "zh-CN",
        }

        with client.websocket_connect(doctor_url) as doctor:
            receive_until(doctor, "client.online")
            with client.websocket_connect(patient_url) as patient:
                receive_until(patient, "client.online")
                doctor.send_json(event(session, "doctor", "question.sent", question))
                assert receive_until(patient, "question.sent")["payload"] == question

                patient.send_json(
                    event(
                        session,
                        "patient",
                        "answer.submitted",
                        answer,
                        event_id="test-event-0002",
                    )
                )
                assert receive_until(doctor, "answer.submitted")["payload"] == answer
                assert receive_until(patient, "answer.received")["payload"] == {
                    "question_id": "question-1"
                }


def test_patient_cannot_send_doctor_only_event(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for(tmp_path))) as client:
        session = create_session(client)
        patient_url = (
            f"/ws/v1/sessions/{session['session_id']}"
            f"?role=patient&token={session['patient_token']}"
        )
        with client.websocket_connect(patient_url) as patient:
            receive_until(patient, "client.online")
            patient.send_json(event(session, "patient", "question.sent"))
            with pytest.raises(WebSocketDisconnect) as rejected:
                patient.receive_json()
            assert rejected.value.code == 4403


def test_session_survives_restart_and_can_be_purged(tmp_path: Path) -> None:
    configured = settings_for(tmp_path)
    with TestClient(create_app(configured)) as first_client:
        session = create_session(first_client)

    with TestClient(create_app(configured)) as restarted_client:
        socket_url = (
            f"/ws/v1/sessions/{session['session_id']}"
            f"?role=doctor&token={session['doctor_token']}"
        )
        with restarted_client.websocket_connect(socket_url) as socket:
            assert receive_until(socket, "client.online")["payload"]["role"] == "doctor"

        deleted = restarted_client.delete(
            f"/api/v1/sessions/{session['session_id']}",
            params={"role": "doctor", "token": session["doctor_token"]},
        )
        assert deleted.status_code == 204

        repository = SessionRepository(configured.database_path)
        assert repository.event_count(session["session_id"]) == 0
        with (
            pytest.raises(WebSocketDisconnect) as rejected,
            restarted_client.websocket_connect(socket_url),
        ):
            pass
        assert rejected.value.code == 4403


def test_patient_cannot_delete_session(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for(tmp_path))) as client:
        session = create_session(client)
        response = client.delete(
            f"/api/v1/sessions/{session['session_id']}",
            params={"role": "patient", "token": session["patient_token"]},
        )
        assert response.status_code == 403
