from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import types

from ai_engine.services.embedding_service import EmbeddingService
from app.core.config import settings


def make_embedding_service(monkeypatch, response=None, side_effect=None):
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "gemini-embedding-001")
    service = EmbeddingService()
    service.client = SimpleNamespace(
        models=SimpleNamespace(
            embed_content=Mock(return_value=response, side_effect=side_effect)
        )
    )
    return service


def test_create_embeddings_uses_configured_model_and_requested_dimension(monkeypatch):
    response = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3])]
    )
    service = make_embedding_service(monkeypatch, response=response)

    embeddings = service.create_embeddings(
        ["Contract clause."],
        output_dimensionality=1536,
    )

    assert embeddings == [[0.1, 0.2, 0.3]]
    service.client.models.embed_content.assert_called_once()
    call = service.client.models.embed_content.call_args.kwargs
    assert call["model"] == "gemini-embedding-001"
    assert call["contents"] == ["Contract clause."]
    assert isinstance(call["config"], types.EmbedContentConfig)
    assert call["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert call["config"].output_dimensionality == 1536


def test_create_embeddings_preserves_query_task_type(monkeypatch):
    response = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3])]
    )
    service = make_embedding_service(monkeypatch, response=response)

    service.create_embeddings(["Question?"], task_type="RETRIEVAL_QUERY")

    assert (
        service.client.models.embed_content.call_args.kwargs["config"].task_type
        == "RETRIEVAL_QUERY"
    )


def test_create_embeddings_surfaces_api_failure_without_legacy_model_fallback(
    monkeypatch,
):
    service = make_embedding_service(
        monkeypatch,
        side_effect=RuntimeError("404 model not found"),
    )

    with pytest.raises(RuntimeError, match="404 model not found"):
        service.create_embeddings(["Contract clause."])

    service.client.models.embed_content.assert_called_once()
