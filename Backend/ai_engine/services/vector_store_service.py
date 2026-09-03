from app.core.config import settings
import chromadb

class VectorStoreService:
    
    
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_PATH
        )
        self.collection = self.client.get_or_create_collection(settings.COLLECTION_NAME)
        
    def _validate_store_input(
        self,
        chunks: list[str],
        embeddings: list[list[float]]
    ):
        if not chunks:
            raise ValueError("Chunk not found.")
        if not embeddings:
            raise ValueError("Embeddings not found.")
        if len(chunks)!=len(embeddings):
            raise ValueError("chunk and embeddings must be same length.")
    
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
        version: int
    ) -> dict[str, int|str]:
        return {
            "contract_id": contract_id,
            "user_id": user_id,
            "chunk_index": chunk_index,
            "analysis_version": version
        }
        
    def store_embeddings(
        self,
        contract_id: int,
        user_id: int,
        chunks: list[str],
        embeddings: list[list[float]],
        version: int
    ) -> None:
        self._validate_store_input(
            chunks=chunks,
            embeddings=embeddings
        )
        ids = [
            self._generate_ids(
                "contract",
                contract_id,
                version,
                index
            )
            for index , _ in enumerate(chunks)
        ]
        metadata = [
            self._build_metadata(
                contract_id,
                user_id,
                index,
                version
            )
            for index , _ in enumerate(chunks)
        ]
        try:
            self.collection.add(
                ids=ids,
                metadatas=metadata,
                embeddings=embeddings,
                documents=chunks
            )
        except Exception as exc:
            raise RuntimeError(
                "Faild to store embeddings."
            )from exc
            
    def search(
        self,
        contract_id: int,
        user_id: int,
        query_embedding: list[float],
        top_k: int = 5
    ) -> list[str]:
        if not query_embedding:
            return []

        c_id = int(contract_id)
        u_id = int(user_id)

        # Helper validator for valid document text chunks
        def is_valid(doc: str) -> bool:
            if not isinstance(doc, str):
                return False
            s = doc.strip()
            if len(s) < 3:
                return False
            if s.isdigit() and len(s) <= 3:
                return False
            return True

        # 1. Try search with contract_id and user_id filter
        try:
            result = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where={"$and": [{"contract_id": c_id}, {"user_id": u_id}]}
            )
            docs = result.get("documents", [])
            if docs and docs[0]:
                valid_docs = [d for d in docs[0] if is_valid(d)]
                if valid_docs:
                    return valid_docs
        except Exception:
            pass

        # 2. Try search with contract_id filter
        try:
            result = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where={"contract_id": c_id}
            )
            docs = result.get("documents", [])
            if docs and docs[0]:
                valid_docs = [d for d in docs[0] if is_valid(d)]
                if valid_docs:
                    return valid_docs
        except Exception:
            pass

        # 3. Fallback: Search top_k without metadata filter
        try:
            result = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            docs = result.get("documents", [])
            if docs and docs[0]:
                valid_docs = [d for d in docs[0] if is_valid(d)]
                if valid_docs:
                    return valid_docs
        except Exception:
            pass

        return []


    