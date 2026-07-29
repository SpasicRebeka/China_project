from collections.abc import AsyncIterable, AsyncIterator

from ..schemas import TranscriptSegment


class NullTranscriptionProvider:
    name = "disabled"
    available = False

    async def transcribe(
        self,
        audio_stream: AsyncIterable[bytes],
        *,
        language: str,
    ) -> AsyncIterator[TranscriptSegment]:
        del language
        async for _ in audio_stream:
            pass
        if False:
            yield TranscriptSegment(
                segment_id="disabled",
                text="",
                is_final=True,
                language="und",
                started_at_ms=0,
            )

