import pytest

from ai_engine.services import chunk_service as chunk_module
from ai_engine.services.chunk_service import ChunkService


def test_chunker_returns_trimmed_text_when_it_fits_in_one_chunk(monkeypatch):
    monkeypatch.setattr(chunk_module, "HAS_LANGCHAIN", False)

    chunks = ChunkService().chunk_text("  A short contract paragraph.  ")

    assert chunks == ["A short contract paragraph."]


def test_fallback_chunker_keeps_configured_overlap(monkeypatch):
    monkeypatch.setattr(chunk_module, "HAS_LANGCHAIN", False)
    text = "a" * (ChunkService.CHUNK_SIZE + 100)

    chunks = ChunkService().chunk_text(text)

    assert len(chunks) == 2
    assert len(chunks[0]) == ChunkService.CHUNK_SIZE
    assert chunks[0][-ChunkService.CHUNK_OVERLAP :] == chunks[1][:ChunkService.CHUNK_OVERLAP]
    assert "".join(
        [chunks[0], chunks[1][ChunkService.CHUNK_OVERLAP :]]
    ) == text


@pytest.mark.parametrize("text", ["", "  \n "])
def test_chunker_rejects_empty_or_whitespace_text(text):
    with pytest.raises(ValueError, match="Text is empty"):
        ChunkService().chunk_text(text)
