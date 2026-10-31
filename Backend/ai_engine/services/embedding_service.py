import os
import time
from typing import Literal

from app.core.config import settings
from ai_engine.logger import get_ai_logger

logger = get_ai_logger("services.embedding")

EmbeddingTaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]

_RETIRED_EMBEDDING_MODELS = {
    "text-embedding-004",
    "models/text-embedding-004",
    "embedding-001",
    "models/embedding-001",
}


class EmbeddingService:
    _MAX_BATCH_SIZE = 50
    _DEFAULT_DIMENSION = 768
    _cached_dimension: int | None = None

    def __init__(self):
        self.api_key = (
            getattr(settings, "GOOGLE_API_KEY", None)
            or getattr(settings, "GEMINI_API_KEY", None)
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        self.client = None
        if self.api_key:
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError(
                    "The google-genai package is required for embeddings."
                ) from exc
            self.client = genai.Client(api_key=self.api_key)

    def _validate_chunks(self, chunks: list[str]) -> list[str]:
        if not chunks:
            raise ValueError("No valid text chunks found in document.")
        cleaned = [
            item.strip() if isinstance(item, str) and item.strip() else "."
            for item in chunks
        ]
        if all(c == "." for c in cleaned):
            raise ValueError("No valid text chunks found in document.")
        return cleaned

    def _resolve_target_dimension(self) -> int:
        if EmbeddingService._cached_dimension is not None:
            return EmbeddingService._cached_dimension

        env_dim = getattr(settings, "EMBEDDING_DIMENSION", None) or os.getenv("EMBEDDING_DIMENSION")
        if env_dim:
            try:
                dim = int(env_dim)
                if 128 <= dim <= 3072:
                    EmbeddingService._cached_dimension = dim
                    return dim
            except ValueError:
                pass

        if getattr(settings, "PINECONE_API_KEY", None) and getattr(settings, "PINECONE_INDEX_NAME", None):
            try:
                from pinecone import Pinecone

                pc = Pinecone(api_key=settings.PINECONE_API_KEY)
                index_names = set(pc.list_indexes().names())
                if settings.PINECONE_INDEX_NAME in index_names:
                    desc = pc.describe_index(settings.PINECONE_INDEX_NAME)
                    actual_dim = getattr(desc, "dimension", None)
                    if isinstance(actual_dim, int) and 128 <= actual_dim <= 3072:
                        EmbeddingService._cached_dimension = actual_dim
                        return actual_dim
            except Exception as exc:
                logger.warning(f"Could not inspect Pinecone index dimension, using default 768: {exc}")

        EmbeddingService._cached_dimension = self._DEFAULT_DIMENSION
        return self._DEFAULT_DIMENSION

    def _candidate_models(self) -> list[str]:
        configured = (getattr(settings, "EMBEDDING_MODEL", "") or "").strip()
        candidates: list[str] = []
        if configured and configured not in _RETIRED_EMBEDDING_MODELS:
            candidates.append(configured)
        for fallback in ("gemini-embedding-001", "gemini-embedding-2-preview", "text-embedding-005"):
            if fallback not in candidates:
                candidates.append(fallback)
        return candidates

    def _call_with_retry(self, model_name: str, batch: list[str], cfg) -> list[list[float]]:
        for attempt in range(3):
            try:
                response = self.client.models.embed_content(
                    model=model_name,
                    contents=batch,
                    config=cfg,
                )
                batch_embeddings = getattr(response, "embeddings", None)
                if not batch_embeddings or len(batch_embeddings) != len(batch):
                    raise ValueError(
                        "Embedding API returned an unexpected number of embeddings."
                    )
                return [list(emb.values) for emb in batch_embeddings]
            except Exception as exc:
                err_text = str(exc).lower()
                is_transient = (
                    "429" in err_text
                    or "resource_exhausted" in err_text
                    or "503" in err_text
                    or "unavailable" in err_text
                )
                if is_transient and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        raise RuntimeError("Embedding retry attempts exhausted.")

    def _embed_batch(
        self,
        batch: list[str],
        task_type: EmbeddingTaskType,
        dimension: int,
    ) -> list[list[float]]:
        from google.genai import types

        last_exc: Exception | None = None
        for model_name in self._candidate_models():
            try:
                return self._call_with_retry(
                    model_name=model_name,
                    batch=batch,
                    cfg=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=dimension,
                    ),
                )
            except Exception as exc:
                last_exc = exc
                err_text = str(exc).lower()
                if "404" in err_text or "not found" in err_text or "not supported" in err_text:
                    continue
                if "400" in err_text or "invalid_argument" in err_text:
                    try:
                        return self._call_with_retry(
                            model_name=model_name,
                            batch=batch,
                            cfg=types.EmbedContentConfig(
                                output_dimensionality=dimension,
                            ),
                        )
                    except Exception as retry_exc:
                        last_exc = retry_exc
                        continue

        raise RuntimeError(f"Failed to generate embeddings: {last_exc}") from last_exc

    def create_embeddings(
        self,
        chunks: list[str],
        task_type: EmbeddingTaskType = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        valid_chunks = self._validate_chunks(chunks)

        if self.client is None:
            raise RuntimeError(
                "A Google/Gemini API key (GEMINI_API_KEY or GOOGLE_API_KEY) is required to generate embeddings."
            )

        dimension = self._resolve_target_dimension()
        embeddings: list[list[float]] = []

        try:
            for start in range(0, len(valid_chunks), self._MAX_BATCH_SIZE):
                batch = valid_chunks[start : start + self._MAX_BATCH_SIZE]
                batch_vectors = self._embed_batch(
                    batch=batch,
                    task_type=task_type,
                    dimension=dimension,
                )
                embeddings.extend(batch_vectors)
            return embeddings
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to generate embeddings: {exc}") from exc