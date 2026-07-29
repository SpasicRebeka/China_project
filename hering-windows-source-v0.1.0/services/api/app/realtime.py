import asyncio
from contextlib import suppress

from fastapi import WebSocket, WebSocketDisconnect

from .schemas import RealtimeEnvelope, Role


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, dict[Role, set[WebSocket]]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, role: Role, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            roles = self._connections.setdefault(session_id, {"doctor": set(), "patient": set()})
            roles[role].add(websocket)

    async def disconnect(self, session_id: str, role: Role, websocket: WebSocket) -> None:
        async with self._lock:
            roles = self._connections.get(session_id)
            if roles is None:
                return
            roles[role].discard(websocket)
            if not roles["doctor"] and not roles["patient"]:
                self._connections.pop(session_id, None)

    async def broadcast(self, session_id: str, envelope: RealtimeEnvelope) -> None:
        await self.send_to_roles(session_id, {"doctor", "patient"}, envelope)

    async def send_to_roles(
        self,
        session_id: str,
        target_roles: set[Role],
        envelope: RealtimeEnvelope,
    ) -> None:
        async with self._lock:
            roles = self._connections.get(session_id, {"doctor": set(), "patient": set()})
            targets = [
                target
                for role in target_roles
                for target in roles[role]
            ]
        stale: list[WebSocket] = []
        for target in targets:
            try:
                await target.send_json(envelope.model_dump(mode="json"))
            except (RuntimeError, WebSocketDisconnect):
                stale.append(target)
        if stale:
            async with self._lock:
                for role_targets in self._connections.get(session_id, {}).values():
                    role_targets.difference_update(stale)

    async def close_session(self, session_id: str) -> None:
        async with self._lock:
            roles = self._connections.pop(session_id, {"doctor": set(), "patient": set()})
            targets = list(roles["doctor"] | roles["patient"])
        for target in targets:
            with suppress(RuntimeError):
                await target.close(code=1000, reason="session ended")
