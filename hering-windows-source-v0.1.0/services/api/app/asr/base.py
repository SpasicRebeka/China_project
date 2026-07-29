from collections.abc import AsyncIterable, AsyncIterator
from typing import Protocol

from ..schemas import TranscriptSegment


class TranscriptionProvider(Protocol):
    """Boundary for a future local or remote streaming ASR implementation."""

    name: str
    available: bool

    def transcribe(
        self,
        audio_stream: AsyncIterable[bytes],
        *,
        language: str,
    ) -> AsyncIterator[TranscriptSegment]: ...

