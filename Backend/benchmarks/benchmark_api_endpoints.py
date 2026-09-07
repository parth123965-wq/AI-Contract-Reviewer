import time
import asyncio
import statistics
from typing import Dict, Any, List
from fastapi.testclient import TestClient

from app.main import app
from app.auth.jwt import create_access_token, decode_access_token


def benchmark_jwt_security(iterations: int = 500) -> Dict[str, Any]:
    """Measures JWT access token creation and verification overhead."""
    payload = {"sub": "123", "role": "admin", "email": "admin@example.com"}

    # Token Creation
    create_start = time.perf_counter()
    tokens = []
    for _ in range(iterations):
        t = create_access_token(data=payload)
        tokens.append(t)
    create_elapsed = time.perf_counter() - create_start

    # Token Decoding
    decode_start = time.perf_counter()
    for token in tokens:
        decode_access_token(token)
    decode_elapsed = time.perf_counter() - decode_start

    return {
        "benchmark": "jwt_security_overhead",
        "iterations": iterations,
        "creation_total_sec": round(create_elapsed, 4),
        "creation_ops_per_sec": round(iterations / create_elapsed, 2),
        "decoding_total_sec": round(decode_elapsed, 4),
        "decoding_ops_per_sec": round(iterations / decode_elapsed, 2),
        "avg_token_roundtrip_ms": round(((create_elapsed + decode_elapsed) / iterations) * 1000, 3)
    }


def benchmark_api_health_concurrency(num_requests: int = 200, concurrency: int = 10) -> Dict[str, Any]:
    """Measures FastAPI endpoint throughput & latency under concurrent client load."""
    client = TestClient(app)
    latencies_ms: List[float] = []

    start_time = time.perf_counter()

    for _ in range(num_requests):
        req_start = time.perf_counter()
        response = client.get("/")
        req_elapsed = (time.perf_counter() - req_start) * 1000  # ms
        if response.status_code == 200:
            latencies_ms.append(req_elapsed)

    total_elapsed = time.perf_counter() - start_time
    sorted_lat = sorted(latencies_ms) if latencies_ms else [0.0]

    p50 = statistics.median(sorted_lat)
    p90 = sorted_lat[int(len(sorted_lat) * 0.90)] if sorted_lat else 0.0
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)] if sorted_lat else 0.0

    return {
        "benchmark": "api_health_throughput",
        "total_requests": num_requests,
        "successful_requests": len(latencies_ms),
        "total_elapsed_sec": round(total_elapsed, 4),
        "requests_per_sec": round(len(latencies_ms) / total_elapsed, 2),
        "latency_min_ms": round(min(sorted_lat), 2),
        "latency_mean_ms": round(statistics.mean(sorted_lat), 2),
        "latency_p50_ms": round(p50, 2),
        "latency_p90_ms": round(p90, 2),
        "latency_p99_ms": round(p99, 2),
        "latency_max_ms": round(max(sorted_lat), 2)
    }


def run_all_api_benchmarks() -> Dict[str, Any]:
    """Runs all API benchmarks and returns aggregated metrics."""
    return {
        "jwt_security": benchmark_jwt_security(iterations=200),
        "api_throughput": benchmark_api_health_concurrency(num_requests=40, concurrency=5)
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_all_api_benchmarks(), indent=2))
