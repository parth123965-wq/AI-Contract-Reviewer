import time
import tempfile
import shutil
import os
from typing import Dict, Any

from ai_engine.services.chunk_service import ChunkService
from ai_engine.services.embedding_service import EmbeddingService
from ai_engine.services.vector_store_service import VectorStoreService


SAMPLE_CONTRACT_TEXT = """
NON-DISCLOSURE AND CONFIDENTIALITY AGREEMENT

This Non-Disclosure Agreement ("Agreement") is entered into as of January 1, 2026, by and between Company A ("Disclosing Party") and Company B ("Receiving Party").

1. PURPOSE & CONFIDENTIAL INFORMATION
The Receiving Party agrees to keep confidential all technical, financial, commercial, and operational information provided by the Disclosing Party. Confidential Information shall include source code, business plans, financial projections, customer data, and contract terms.

2. OBLIGATIONS & RESTRICTIONS
The Receiving Party shall exercise reasonable care to protect Confidential Information, using at least the same degree of care it uses for its own confidential materials of similar nature. The Receiving Party shall not disclose Confidential Information to third parties without prior written approval.

3. INDEMNIFICATION & LIABILITY
Each party agrees to defend, indemnify, and hold harmless the other party against any claims, losses, damages, or liabilities arising out of a material breach of this Agreement. In no event shall either party's aggregate liability under this Agreement exceed $1,000,000 USD.

4. GOVERNING LAW & TERMINATION
This Agreement shall be governed by the laws of the State of Delaware. Either party may terminate this Agreement upon 30 days written notice. Obligations regarding confidentiality shall survive for 5 years following termination.
""" * 10  # Multiply to create a realistic multi-page contract string (~12KB)


def benchmark_chunking(iterations: int = 50) -> Dict[str, Any]:
    """Measures document text chunking throughput."""
    chunker = ChunkService()
    start_time = time.perf_counter()
    total_chunks = 0
    total_chars = 0

    for _ in range(iterations):
        chunks = chunker.chunk_text(SAMPLE_CONTRACT_TEXT)
        total_chunks += len(chunks)
        total_chars += len(SAMPLE_CONTRACT_TEXT)

    elapsed = time.perf_counter() - start_time
    return {
        "benchmark": "text_chunking",
        "iterations": iterations,
        "total_elapsed_sec": round(elapsed, 4),
        "avg_ms_per_call": round((elapsed / iterations) * 1000, 2),
        "chunks_per_sec": round(total_chunks / elapsed, 2),
        "chars_per_sec": round(total_chars / elapsed, 2)
    }


def benchmark_embeddings(num_chunks: int = 20) -> Dict[str, Any]:
    """Measures sentence-transformers embedding generation performance."""
    chunker = ChunkService()
    embedding_svc = EmbeddingService()
    sample_chunks = chunker.chunk_text(SAMPLE_CONTRACT_TEXT)[:num_chunks]

    start_time = time.perf_counter()
    embeddings = embedding_svc.create_embeddings(sample_chunks)
    elapsed = time.perf_counter() - start_time

    return {
        "benchmark": "embedding_generation",
        "chunks_processed": len(sample_chunks),
        "embedding_dimensions": len(embeddings[0]) if embeddings else 0,
        "total_elapsed_sec": round(elapsed, 4),
        "avg_ms_per_chunk": round((elapsed / len(sample_chunks)) * 1000, 2),
        "chunks_per_sec": round(len(sample_chunks) / elapsed, 2)
    }


def benchmark_vector_store(vector_count: int = 50, num_queries: int = 20) -> Dict[str, Any]:
    """Measures ChromaDB insertion rate and Top-K similarity search query latency."""
    temp_dir = tempfile.mkdtemp(prefix="chroma_bench_")
    try:
        # Override temp path for isolated benchmark
        from app.core.config import settings
        orig_path = settings.CHROMA_DB_PATH
        settings.CHROMA_DB_PATH = temp_dir
        
        vec_store = VectorStoreService()
        chunker = ChunkService()
        embedding_svc = EmbeddingService()

        # Generate sample embeddings
        chunks = [f"Contract clause sample chunk #{i}: {SAMPLE_CONTRACT_TEXT[:200]}" for i in range(vector_count)]
        embeddings = embedding_svc.create_embeddings(chunks)

        # Measure Insertion
        store_start = time.perf_counter()
        vec_store.store_embeddings(
            contract_id=999,
            user_id=1,
            chunks=chunks,
            embeddings=embeddings,
            version=1
        )
        store_elapsed = time.perf_counter() - store_start

        # Measure Search Latency
        query_emb = embeddings[0]
        query_start = time.perf_counter()
        for _ in range(num_queries):
            vec_store.search(contract_id=999, user_id=1, query_embedding=query_emb, top_k=5)
        query_elapsed = time.perf_counter() - query_start

        settings.CHROMA_DB_PATH = orig_path

        return {
            "benchmark": "vector_store_chromadb",
            "vectors_stored": vector_count,
            "insertion_time_sec": round(store_elapsed, 4),
            "insertion_rate_vec_per_sec": round(vector_count / store_elapsed, 2),
            "queries_executed": num_queries,
            "total_query_time_sec": round(query_elapsed, 4),
            "avg_query_latency_ms": round((query_elapsed / num_queries) * 1000, 2),
            "queries_per_sec": round(num_queries / query_elapsed, 2)
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_all_ai_benchmarks() -> Dict[str, Any]:
    """Runs all AI pipeline benchmarks and returns aggregated metrics."""
    return {
        "chunking": benchmark_chunking(),
        "embeddings": benchmark_embeddings(),
        "vector_store": benchmark_vector_store()
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_all_ai_benchmarks(), indent=2))
