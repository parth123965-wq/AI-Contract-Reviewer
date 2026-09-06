import json
import time
from datetime import datetime
from pathlib import Path

from benchmarks.benchmark_ai_pipeline import run_all_ai_benchmarks
from benchmarks.benchmark_api_endpoints import run_all_api_benchmarks
from benchmarks.benchmark_resources import get_system_resource_metrics


def generate_markdown_report(metrics: dict, output_path: Path):
    """Formats benchmark results into a clean GitHub-style Markdown report."""
    ai = metrics.get("ai_pipeline", {})
    api = metrics.get("api_endpoints", {})
    res = metrics.get("system_resources", {})

    chunk = ai.get("chunking", {})
    emb = ai.get("embeddings", {})
    vec = ai.get("vector_store", {})
    jwt = api.get("jwt_security", {})
    throughput = api.get("api_throughput", {})

    md_content = f"""# 📊 AI Contract Reviewer - Performance Benchmark Report

**Generated At**: {metrics.get("timestamp")}  
**Environment**: Python, FastAPI, SentenceTransformers (`BAAI/bge-small-en-v1.5`), ChromaDB  

---

## ⚡ 1. AI Pipeline Performance

| Metric | Result | Description |
| :--- | :--- | :--- |
| **Chunking Speed** | `{chunk.get('chars_per_sec', 0):,} chars/sec` | Document splitting throughput (`ChunkService`) |
| **Chunk Output Rate** | `{chunk.get('chunks_per_sec', 0)} chunks/sec` | Chunks generated per second |
| **Embedding Speed** | `{emb.get('avg_ms_per_chunk', 0)} ms/chunk` | Latency per chunk (`sentence-transformers`) |
| **Embedding Rate** | `{emb.get('chunks_per_sec', 0)} chunks/sec` | Embedding generation throughput |
| **Vector Store Insert** | `{vec.get('insertion_rate_vec_per_sec', 0)} vec/sec` | ChromaDB vector insertion throughput |
| **Vector Search Latency** | `{vec.get('avg_query_latency_ms', 0)} ms` | Top-5 similarity search query latency |
| **Vector Search Rate** | `{vec.get('queries_per_sec', 0)} queries/sec` | ChromaDB query throughput |

---

## 🚀 2. API Endpoint & Security Overhead

| Metric | Result | Description |
| :--- | :--- | :--- |
| **JWT Creation Rate** | `{jwt.get('creation_ops_per_sec', 0):,} ops/sec` | Token generation speed |
| **JWT Decoding Rate** | `{jwt.get('decoding_ops_per_sec', 0):,} ops/sec` | Token verification speed |
| **API Throughput** | `{throughput.get('requests_per_sec', 0):,} req/sec` | Health endpoint request rate |
| **Latency ($p_{50}$)** | `{throughput.get('latency_p50_ms', 0)} ms` | Median request latency |
| **Latency ($p_{90}$)** | `{throughput.get('latency_p90_ms', 0)} ms` | 90th percentile latency |
| **Latency ($p_{99}$)** | `{throughput.get('latency_p99_ms', 0)} ms` | 99th percentile latency |

---

## 💻 3. System Resource Utilization

| Resource | Value | Description |
| :--- | :--- | :--- |
| **Process Memory (RSS)** | `{res.get('memory_rss_mb', 0)} MB` | Resident RAM consumed by process |
| **Process CPU** | `{res.get('cpu_percent', 0)}%` | CPU utilization percentage |
| **Active Threads** | `{res.get('num_threads', 0)}` | Worker threads |
| **System RAM Usage** | `{res.get('system_ram_usage_percent', 0)}%` | Total system RAM utilization |

---
"""
    output_path.write_text(md_content, encoding="utf-8")


def main():
    print("=" * 65)
    print(" Running AI Contract Reviewer Performance Benchmark Suite")
    print("=" * 65)

    start_time = time.perf_counter()

    print("\n[1/3] Benchmarking AI Engine Pipeline (Chunking, Embeddings, ChromaDB)...")
    ai_metrics = run_all_ai_benchmarks()

    print("[2/3] Benchmarking API REST Endpoints & Security Overhead...")
    api_metrics = run_all_api_benchmarks()

    print("[3/3] Profiling System Resource Utilization...")
    resource_metrics = get_system_resource_metrics()

    total_time = time.perf_counter() - start_time

    results = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_benchmark_duration_sec": round(total_time, 2),
        "ai_pipeline": ai_metrics,
        "api_endpoints": api_metrics,
        "system_resources": resource_metrics
    }

    # Save JSON Report
    json_path = Path("benchmark_report.json")
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n[OK] JSON report saved to: {json_path.resolve()}")

    # Save Markdown Report
    md_path = Path("benchmark_report.md")
    generate_markdown_report(results, md_path)
    print(f"[OK] Markdown report saved to: {md_path.resolve()}")

    print("\n" + "=" * 65)
    print(" SUMMARY RESULTS")
    print("=" * 65)
    print(f"  * AI Chunking Speed      : {ai_metrics['chunking']['chars_per_sec']:,} chars/sec")
    print(f"  * AI Embedding Latency   : {ai_metrics['embeddings']['avg_ms_per_chunk']} ms / chunk")
    print(f"  * ChromaDB Search Latency: {ai_metrics['vector_store']['avg_query_latency_ms']} ms")
    print(f"  * JWT Encoding Speed     : {api_metrics['jwt_security']['creation_ops_per_sec']:,} ops/sec")
    print(f"  * API Request Rate       : {api_metrics['api_throughput']['requests_per_sec']:,} req/sec")
    print(f"  * Process RAM Usage      : {resource_metrics['memory_rss_mb']} MB")
    print(f"  * Total Benchmark Time   : {round(total_time, 2)}s")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
