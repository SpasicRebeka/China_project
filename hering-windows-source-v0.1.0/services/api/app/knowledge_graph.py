import json
from pathlib import Path
from threading import Lock
from typing import Any


class KnowledgeGraphUnavailable(RuntimeError):
    pass


class KnowledgeGraphStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = Lock()
        self._cached_mtime_ns: int | None = None
        self._cached_payload: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        try:
            mtime_ns = self._path.stat().st_mtime_ns
        except OSError as exc:
            raise KnowledgeGraphUnavailable("knowledge graph file is unavailable") from exc

        with self._lock:
            if self._cached_payload is not None and self._cached_mtime_ns == mtime_ns:
                return self._cached_payload

            try:
                with self._path.open("r", encoding="utf-8") as source:
                    payload = json.load(source)
            except (OSError, json.JSONDecodeError) as exc:
                raise KnowledgeGraphUnavailable("knowledge graph file is invalid") from exc

            if not isinstance(payload, dict):
                raise KnowledgeGraphUnavailable("knowledge graph root must be an object")
            if not isinstance(payload.get("kb_version"), str):
                raise KnowledgeGraphUnavailable("knowledge graph version is missing")
            symptoms = payload.get("symptoms")
            if not isinstance(symptoms, list) or not symptoms:
                raise KnowledgeGraphUnavailable("knowledge graph symptoms are missing")

            self._cached_mtime_ns = mtime_ns
            self._cached_payload = payload
            return payload

