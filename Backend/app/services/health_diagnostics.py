import asyncio
import os
import threading
import time
from pathlib import Path
from typing import Literal, Optional

import psutil
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.core.logger import get_app_logger, get_recent_logs
from app.schemas.admin import (
    AdminDiagnosticsResponse,
    AdminLogTailResponse,
    DatabaseDiagnostics,
)

diagnostics_logger = get_app_logger("health_diagnostics")
_PROCESS_START_TIME = time.monotonic()


def _read_cgroup_value(path: str) -> Optional[str]:
    try:
        return Path(path).read_text(encoding="ascii").strip()
    except FileNotFoundError:
        return None


def _get_memory_limit_bytes() -> int:
    value = _read_cgroup_value("/sys/fs/cgroup/memory.max")
    if value is None:
        value = _read_cgroup_value(
            "/sys/fs/cgroup/memory/memory.limit_in_bytes"
        )
    if value and value != "max":
        limit = int(value)
        if 0 < limit < 2**60:
            return limit
    return psutil.virtual_memory().total


def _get_cpu_quota_cores() -> float:
    value = _read_cgroup_value("/sys/fs/cgroup/cpu.max")
    if value:
        quota, period = value.split()
        if quota != "max":
            return max(float(quota) / float(period), 0.01)

    quota = _read_cgroup_value(
        "/sys/fs/cgroup/cpu/cpu.cfs_quota_us"
    )
    period = _read_cgroup_value(
        "/sys/fs/cgroup/cpu/cpu.cfs_period_us"
    )
    if quota and period and int(quota) > 0:
        return max(int(quota) / int(period), 0.01)

    process = psutil.Process()
    try:
        return float(len(process.cpu_affinity()))
    except (AttributeError, NotImplementedError, psutil.Error):
        return float(psutil.cpu_count(logical=True) or 1)


async def _get_cpu_usage_percent() -> float:
    process = psutil.Process(os.getpid())
    usage_per_core = await asyncio.to_thread(process.cpu_percent, 0.1)
    return round(usage_per_core / _get_cpu_quota_cores(), 2)


def _get_memory_usage() -> tuple[int, int, float]:
    process_memory = psutil.Process(os.getpid()).memory_info().rss
    memory_limit = _get_memory_limit_bytes()
    percentage = round(process_memory / memory_limit * 100, 2)
    return process_memory, memory_limit, percentage


def _get_disk_usage() -> tuple[int, int, float]:
    usage = psutil.disk_usage(str(Path(__file__).resolve().parents[2]))
    return usage.used, usage.total, usage.percent


async def _get_database_diagnostics(
    db: AsyncSession,
) -> DatabaseDiagnostics:
    started_at = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        diagnostics_logger.exception(
            "Database diagnostics query failed",
            extra={"error_type": type(exc).__name__},
        )
        return DatabaseDiagnostics(
            connected=False,
            status="critical",
            latency_ms=None,
            error=type(exc).__name__,
        )
    return DatabaseDiagnostics(
        connected=True,
        status="healthy",
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        error=None,
    )


async def get_system_diagnostics(db: AsyncSession) -> AdminDiagnosticsResponse:
    database = await _get_database_diagnostics(db)
    cpu_percent, memory_usage, disk_usage = await asyncio.gather(
        _get_cpu_usage_percent(),
        asyncio.to_thread(_get_memory_usage),
        asyncio.to_thread(_get_disk_usage),
    )
    process_memory, memory_limit, memory_percent = memory_usage
    disk_used, disk_total, disk_percent = disk_usage

    critical = (
        not database.connected
        or cpu_percent >= 95
        or memory_percent >= 90
        or disk_percent >= 95
    )
    warning = (
        cpu_percent >= 80
        or memory_percent >= 80
        or disk_percent >= 85
        or (database.latency_ms is not None and database.latency_ms >= 1000)
    )
    overall_status: Literal["healthy", "warning", "critical"] = (
        "critical" if critical else "warning" if warning else "healthy"
    )

    return AdminDiagnosticsResponse(
        overall_status=overall_status,
        uptime_seconds=round(time.monotonic() - _PROCESS_START_TIME, 2),
        cpu_percent=cpu_percent,
        process_memory_bytes=process_memory,
        memory_limit_bytes=memory_limit,
        memory_percent=memory_percent,
        disk_used_bytes=disk_used,
        disk_total_bytes=disk_total,
        disk_percent=disk_percent,
        database=database,
        active_thread_count=threading.active_count(),
    )


def get_log_tail(limit: int) -> AdminLogTailResponse:
    return AdminLogTailResponse(logs=get_recent_logs(limit=limit))
