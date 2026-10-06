import time

from pinecone import Pinecone, ServerlessSpec

from app.core.config import settings
from ai_engine.logger import get_ai_logger

logger = get_ai_logger("services.vector_store")


class VectorStoreService:
    def __init__(self):
        if not settings.PINECONE_API_KEY:
            raise RuntimeError("PINECONE_API_KEY is required for vector storage.")
        self.client = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index = None
        self._index_dimension: int | None = None

    def _validate_store_input(
        self,
        chunks: list[str],
        embeddings: list[list[float]]
    ):
        if not chunks:
            raise ValueError("Chunk not found.")
        if not embeddings:
            raise ValueError("Embeddings not found.")
        if len(chunks) != len(embeddings):
            raise ValueError("chunk and embeddings must be same length.")
        if any(not embedding for embedding in embeddings):
            raise ValueError("Embeddings must not be empty.")
        dimensions = {len(embedding) for embedding in embeddings}
        if len(dimensions) != 1:
            raise ValueError("All embeddings must have the same dimension.")

    def _generate_ids(
        self,
        doc_name: str,
        doc_id: int | str,
        version: int,
        chunk_index: int
    ) -> str:
        return f"{doc_name}_{doc_id}_v{version}_chunk_{chunk_index}"

    def _build_metadata(
        self,
        contract_id: int,
        user_id: int,
        chunk_index: int,
        version: int,
        text: str
    ) -> dict[str, int | str]:
        return {
            "contract_id": contract_id,
            "user_id": user_id,
            "chunk_index": chunk_index,
            "analysis_version": version,
            "text": text,
        }

    def _index_names(self) -> set[str]:
        return set(self.client.list_indexes().names())

    def _get_index(self, dimension: int | None = None):
        index_name = settings.PINECONE_INDEX_NAME
        if self.index is not None:
            if dimension is not None and self._index_dimension != dimension:
                raise ValueError(
                    f"Embedding dimension {dimension} does not match Pinecone "
                    f"index dimension {self._index_dimension}."
                )
            return self.index

        if index_name not in self._index_names():
            if dimension is None:
                raise RuntimeError(
                    f"Pinecone index '{index_name}' does not exist yet. "
                    "Store embeddings before searching."
                )
            logger.info(
                "Creating Pinecone index '%s' with dimension %d.",
                index_name,
                dimension,
            )
            self.client.create_index(
                name=index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=settings.PINECONE_CLOUD,
                    region=settings.PINECONE_REGION,
                ),
            )

        deadline = time.monotonic() + 120
        while True:
            description = self.client.describe_index(index_name)
            index_status = description.status
            ready = (
                index_status.get("ready", False)
                if isinstance(index_status, dict)
                else getattr(index_status, "ready", False)
            )
            if ready:
                actual_dimension = description.dimension
                if dimension is not None and actual_dimension != dimension:
                    raise ValueError(
                        f"Embedding dimension {dimension} does not match Pinecone "
                        f"index dimension {actual_dimension}."
                    )
                self._index_dimension = actual_dimension
                self.index = self.client.Index(index_name)
                return self.index
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Pinecone index '{index_name}' was not ready within 120 seconds."
                )
            time.sleep(2)

    def store_embeddings(
        self,
        contract_id: int,
        user_id: int,
        chunks: list[str],
        embeddings: list[list[float]],
        version: int
    ) -> None:
        self._validate_store_input(chunks=chunks, embeddings=embeddings)
        dimension = len(embeddings[0])
        vectors = [
            {
                "id": self._generate_ids("contract", contract_id, version, index),
                "values": embedding,
                "metadata": self._build_metadata(
                    contract_id=contract_id,
                    user_id=user_id,
                    chunk_index=index,
                    version=version,
                    text=chunk,
                ),
            }
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        try:
            self._get_index(dimension=dimension).upsert(vectors=vectors)
        except Exception as exc:
            logger.exception(
                "Failed to store embeddings in Pinecone.",
                extra={"contract_id": contract_id, "user_id": user_id},
            )
            raise RuntimeError("Failed to store embeddings in Pinecone.") from exc

    def search(
        self,
        contract_id: int,
        user_id: int,
        query_embedding: list[float],
        top_k: int = 5
    ) -> list[str]:
        if not query_embedding:
            return []
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        def is_valid(doc: str) -> bool:
            if not isinstance(doc, str):
                return False
            text = doc.strip()
            if len(text) < 3:
                return False
            if text.isdigit() and len(text) <= 3:
                return False
            return True

        try:
            result = self._get_index(dimension=len(query_embedding)).query(
                vector=query_embedding,
                top_k=top_k,
                filter={
                    "contract_id": {"$eq": int(contract_id)},
                    "user_id": {"$eq": int(user_id)},
                },
                include_metadata=True,
            )
            matches = (
                result.get("matches", [])
                if isinstance(result, dict)
                else result.matches
            )
            documents = []
            for match in matches:
                metadata = (
                    match.get("metadata", {})
                    if isinstance(match, dict)
                    else match.metadata or {}
                )
                text = metadata.get("text")
                if is_valid(text):
                    documents.append(text)
            return documents
        except Exception:
            logger.exception(
                "Failed to search Pinecone.",
                extra={"contract_id": contract_id, "user_id": user_id},
            )
            raise
