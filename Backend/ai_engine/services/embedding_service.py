import os
from typing import Literal

from app.core.config import settings

EmbeddingTaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


class EmbeddingService:
    _MAX_BATCH_SIZE = 100

    def __init__(self):
        self.api_key = (
            settings.GOOGLE_API_KEY
            or settings.GEMINI_API_KEY
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
        cleaned = [
            item.strip()
            for item in chunks
            if isinstance(item, str) and item.strip()
        ]
        if not cleaned:
            raise ValueError("No valid text chunks found in document.")
        return cleaned

    def create_embeddings(
        self,
        chunks: list[str],
        task_type: EmbeddingTaskType = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        valid_chunks = self._validate_chunks(chunks)
        if self.client is None:
            raise RuntimeError(
                "A Google API key is required to generate embeddings."
            )

        embeddings: list[list[float]] = []
        try:
            for start in range(0, len(valid_chunks), self._MAX_BATCH_SIZE):
                batch = valid_chunks[start : start + self._MAX_BATCH_SIZE]
                response = self.client.models.embed_content(
                    model=settings.EMBEDDING_MODEL,
                    contents=batch,
                    config={"task_type": task_type},
                )
                batch_embeddings = response.embeddings
                if batch_embeddings is None or len(batch_embeddings) != len(batch):
                    raise ValueError(
                        "Embedding API returned an unexpected number of embeddings."
                    )
                embeddings.extend(
                    [embedding.values for embedding in batch_embeddings]
                )
            return embeddings
        except Exception as exc:
            raise RuntimeError("Failed to generate embeddings") from exc
