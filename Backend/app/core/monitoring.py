"""
=========================================================
SYSTEM MONITORING MODULE

Responsibilities:
- Gather CPU, Memory, and Disk usage metrics.
- Monitor Python application process stats (PID, threads, RSS memory).
- Inspect database connection health & latency.
- Inspect Redis cache connection health & latency.
- Expose consolidated operational health reports.
=========================================================
"""

import os
import sys
import time
import platform
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.logger import get_app_logger
from app.core.redis_setup import get_redis

monitoring_logger = get_app_logger("monitoring")
START_TIME = time.time()


def get_system_resources() -> Dict[str, Any]:
    """Retrieve OS-level CPU, Memory, and Disk usage information."""
    try:
        import psutil
        
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        return {
            "cpu": {
                "usage_percent": psutil.cpu_percent(interval=0.1),
                "core_count": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False),
            },
            "memory": {
                "total_bytes": vm.total,
                "available_bytes": vm.available,
                "used_bytes": vm.used,
                "usage_percent": vm.percent,
            },
            "disk": {
                "total_bytes": disk.total,
                "used_bytes": disk.used,
                "free_bytes": disk.free,
                "usage_percent": disk.percent,
            }
        }
    except Exception as e:
        monitoring_logger.warning("Error fetching psutil system resources", extra={"error": str(e)})
        return {
            "cpu": {"usage_percent": 0.0, "core_count": os.cpu_count() or 1},
            "memory": {"usage_percent": 0.0},
            "disk": {"usage_percent": 0.0},
            "error": str(e)
        }


def get_process_metrics() -> Dict[str, Any]:
    """Retrieve current Python process execution details and uptime."""
    uptime_seconds = round(time.time() - START_TIME, 2)
    process_info: Dict[str, Any] = {
        "pid": os.getpid(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "uptime_seconds": uptime_seconds,
        "uptime_formatted": f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m {int(uptime_seconds % 60)}s",
    }
    
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem_info = proc.memory_info()
        process_info.update({
            "memory_rss_bytes": mem_info.rss,
            "memory_vms_bytes": mem_info.vms,
            "cpu_percent": proc.cpu_percent(interval=0.0),
            "num_threads": proc.num_threads(),
        })
    except Exception as e:
        monitoring_logger.warning("Error fetching process metrics", extra={"error": str(e)})
        
    return process_info


async def get_db_health(db: AsyncSession) -> Dict[str, Any]:
    """Check relational database connection status and execution latency."""
    start_t = time.time()
    try:
        result = await db.execute(text("SELECT 1"))
        val = result.scalar()
        latency_ms = round((time.time() - start_t) * 1000, 2)
        if val == 1:
            return {
                "status": "healthy",
                "latency_ms": latency_ms,
                "connected": True
            }
        else:
            return {
                "status": "unhealthy",
                "latency_ms": latency_ms,
                "connected": False,
                "error": "Unexpected query response"
            }
    except Exception as e:
        latency_ms = round((time.time() - start_t) * 1000, 2)
        monitoring_logger.error("Database health check failed", extra={"error": str(e)})
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "connected": False,
            "error": str(e)
        }


async def get_redis_health() -> Dict[str, Any]:
    """Check Redis cache service connection status and latency."""
    start_t = time.time()
    try:
        client = await get_redis()
        if client is None:
            return {
                "status": "disabled",
                "connected": False,
                "latency_ms": 0.0,
                "message": "Redis client not initialized"
            }
        
        ping_ok = await client.ping()
        latency_ms = round((time.time() - start_t) * 1000, 2)
        if ping_ok:
            info = await client.info("memory")
            used_memory = info.get("used_memory_human", "N/A") if isinstance(info, dict) else "N/A"
            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": latency_ms,
                "used_memory_human": used_memory
            }
        return {
            "status": "unhealthy",
            "connected": False,
            "latency_ms": latency_ms,
            "message": "Ping returned False"
        }
    except Exception as e:
        latency_ms = round((time.time() - start_t) * 1000, 2)
        monitoring_logger.warning("Redis health check warning", extra={"error": str(e)})
        return {
            "status": "unhealthy",
            "connected": False,
            "latency_ms": latency_ms,
            "error": str(e)
        }


# =========================================================
# PERFORMANCE METRICS TRACKER (IN-MEMORY TELEMETRY)
# =========================================================

class PerformanceTracker:
    def __init__(self, max_samples: int = 100):
        self.max_samples = max_samples
        self.http_latencies = []
        self.llm_latencies = []
        self.vector_latencies = []
        self.db_latencies = []
        self.llm_errors = 0

    def record_http_request(self, duration_ms: float):
        self.http_latencies.append(duration_ms)
        if len(self.http_latencies) > self.max_samples:
            self.http_latencies.pop(0)

    def record_llm_call(self, duration_ms: float, success: bool = True):
        self.llm_latencies.append(duration_ms)
        if not success:
            self.llm_errors += 1
        if len(self.llm_latencies) > self.max_samples:
            self.llm_latencies.pop(0)

    def record_vector_search(self, duration_ms: float):
        self.vector_latencies.append(duration_ms)
        if len(self.vector_latencies) > self.max_samples:
            self.vector_latencies.pop(0)

    def record_db_query(self, duration_ms: float):
        self.db_latencies.append(duration_ms)
        if len(self.db_latencies) > self.max_samples:
            self.db_latencies.pop(0)

    def _calc_stats(self, latencies: list) -> Dict[str, Any]:
        if not latencies:
            return {"count": 0, "avg_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "p95_ms": 0.0}
        sorted_l = sorted(latencies)
        p95_idx = int(len(sorted_l) * 0.95)
        return {
            "count": len(latencies),
            "avg_ms": round(sum(latencies) / len(latencies), 2),
            "min_ms": round(sorted_l[0], 2),
            "max_ms": round(sorted_l[-1], 2),
            "p95_ms": round(sorted_l[min(p95_idx, len(sorted_l) - 1)], 2)
        }

    def get_report(self) -> Dict[str, Any]:
        http_stats = self._calc_stats(self.http_latencies)
        
        # Build histogram buckets for HTTP request response times
        buckets = {"<50ms": 0, "50-200ms": 0, "200-500ms": 0, ">500ms": 0}
        for lat in self.http_latencies:
            if lat < 50:
                buckets["<50ms"] += 1
            elif lat <= 200:
                buckets["50-200ms"] += 1
            elif lat <= 500:
                buckets["200-500ms"] += 1
            else:
                buckets[">500ms"] += 1

        http_stats["histogram"] = buckets

        llm_stats = self._calc_stats(self.llm_latencies)
        llm_stats["error_count"] = self.llm_errors

        vector_stats = self._calc_stats(self.vector_latencies)
        db_stats = self._calc_stats(self.db_latencies)

        return {
            "http_requests": http_stats,
            "llm_api_calls": llm_stats,
            "vector_search": vector_stats,
            "database_queries": db_stats,
        }


perf_tracker = PerformanceTracker()


def record_http_request(duration_ms: float):
    perf_tracker.record_http_request(duration_ms)


def record_llm_call(duration_ms: float, success: bool = True):
    perf_tracker.record_llm_call(duration_ms, success)


def record_vector_search(duration_ms: float):
    perf_tracker.record_vector_search(duration_ms)


def record_db_query(duration_ms: float):
    perf_tracker.record_db_query(duration_ms)


async def get_full_monitoring_report(db: AsyncSession) -> Dict[str, Any]:
    """Generates comprehensive system monitoring report."""
    db_health = await get_db_health(db)
    redis_health = await get_redis_health()
    sys_resources = get_system_resources()
    proc_metrics = get_process_metrics()
    perf_metrics = perf_tracker.get_report()

    # Track db check latency into telemetry
    if "latency_ms" in db_health:
        record_db_query(db_health["latency_ms"])

    is_overall_healthy = (
        db_health.get("connected", False) and 
        redis_health.get("status") in ["healthy", "disabled"]
    )

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "overall_status": "healthy" if is_overall_healthy else "degraded",
        "system": sys_resources,
        "process": proc_metrics,
        "services": {
            "database": db_health,
            "redis": redis_health,
        },
        "performance": perf_metrics
    }

