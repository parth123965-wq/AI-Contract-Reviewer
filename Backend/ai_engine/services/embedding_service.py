import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

from app.core.config import settings

class EmbeddingService:
    
    def __init__(self):
        if HAS_SENTENCE_TRANSFORMERS:
            self.model = SentenceTransformer(settings.MODEL_NAME)
        else:
            self.model = None
        
    def _validate_chunks(
        self,
        chunks: list[str]
    ) -> list[str]:
        cleaned = [item.strip() for item in chunks if isinstance(item, str) and item.strip()]
        if not cleaned:
            raise ValueError("No valid text chunks found in document.")
        return cleaned
        
    def create_embeddings(
        self,
        chunks: list[str]
    ) -> list[list[float]]:
        valid_chunks = self._validate_chunks(chunks=chunks)
        try:
            embeddings = self.model.encode(valid_chunks)
            return embeddings.tolist()
        except Exception as exc:
            raise RuntimeError("Failed to generate embeddings") from exc