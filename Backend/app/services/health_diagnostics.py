import asyncio
import os
import threading
import time
from pathlib import Path
from typing import Callable, Literal, Optional

import httpx
import psutil
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.core import redis_setup
from app.core.config import settings
from app.core.logger import get_app_logger, get_recent_logs
from app.services.contract_storage import ContractStorage
from app.schemas.admin import (
    AdminDiagnosticsResponse,
    AdminLogTailResponse,
    DependencyDiagnostics,
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


def _get_disk_usage() -> tuple[str, int, int, float]:
    render_disk_path = Path("/var/data")
    disk_path = (
        render_disk_path
        if render_disk_path.exists() and os.path.ismount(render_disk_path)
        else Path(__file__).resolve().parents[2]
    )
    usage = psutil.disk_usage(str(disk_path))
    return str(disk_path), usage.used, usage.total, usage.percent


async def _get_database_diagnostics(
    db: AsyncSession,
) -> DependencyDiagnostics:
    started_at = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        diagnostics_logger.exception(
            "Database diagnostics query failed",
            extra={"error_type": type(exc).__name__},
        )
        return DependencyDiagnostics(
            connected=False,
            status="critical",
            latency_ms=None,
            error=type(exc).__name__,
        )
    return DependencyDiagnostics(
        connected=True,
        status="healthy",
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        error=None,
    )


async def _run_sync_dependency_check(
    checker: Callable[[], None],
) -> DependencyDiagnostics:
    started_at = time.perf_counter()
    try:
        await asyncio.to_thread(checker)
    except Exception as exc:
        diagnostics_logger.warning(
            "External dependency health check failed.",
            extra={"error_type": type(exc).__name__},
        )
        return DependencyDiagnostics(
            connected=False,
            status="critical",
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            error=type(exc).__name__,
        )
    return DependencyDiagnostics(
        connected=True,
        status="healthy",
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )


async def _get_vector_store_diagnostics() -> DependencyDiagnostics:
    def check_vector_store() -> None:
        if not settings.PINECONE_API_KEY:
            raise RuntimeError("Pinecone API key is not configured.")
        from pinecone import Pinecone

        client = Pinecone(api_key=settings.PINECONE_API_KEY)
        index_names = set(client.list_indexes().names())
        if settings.PINECONE_INDEX_NAME not in index_names:
            raise LookupError("Configured Pinecone index does not exist.")
        description = client.describe_index(settings.PINECONE_INDEX_NAME)
        index_status = description.status
        ready = (
            index_status.get("ready", False)
            if isinstance(index_status, dict)
            else getattr(index_status, "ready", False)
        )
        if not ready:
            raise RuntimeError("Configured Pinecone index is not ready.")

    return await _run_sync_dependency_check(check_vector_store)


async def _get_supabase_storage_diagnostics() -> DependencyDiagnostics:
    def check_supabase_storage() -> None:
        storage = ContractStorage().client.storage
        storage.get_bucket(ContractStorage.BUCKET_NAME)

    return await _run_sync_dependency_check(check_supabase_storage)


async def _get_redis_diagnostics() -> DependencyDiagnostics:
    started_at = time.perf_counter()
    client = redis_setup.redis_client
    if client is None:
        return DependencyDiagnostics(
            connected=False,
            status="critical",
            latency_ms=None,
            error="NotInitialized",
        )
    try:
        await client.ping()
    except Exception as exc:
        diagnostics_logger.warning(
            "Redis health check failed.",
            extra={"error_type": type(exc).__name__},
        )
        return DependencyDiagnostics(
            connected=False,
            status="critical",
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            error=type(exc).__name__,
        )
    return DependencyDiagnostics(
        connected=True,
        status="healthy",
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )


async def _get_email_diagnostics() -> DependencyDiagnostics:
    started_at = time.perf_counter()
    if not settings.BREVO_API_KEY or not settings.GMAIL_SENDER:
        return DependencyDiagnostics(
            connected=False,
            status="critical",
            latency_ms=None,
            error="ConfigurationMissing",
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.brevo.com/v3/senders",
                headers={
                    "api-key": settings.BREVO_API_KEY,
                    "accept": "application/json",
                },
            )
            response.raise_for_status()
        senders = response.json().get("senders", [])
        sender_is_active = any(
            sender.get("email", "").casefold() == settings.GMAIL_SENDER.casefold()
            and sender.get("active") is True
            for sender in senders
        )
        if not sender_is_active:
            return DependencyDiagnostics(
                connected=False,
                status="critical",
                latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
                error="ConfiguredSenderMissingOrInactive",
            )
    except Exception as exc:
        diagnostics_logger.warning(
            "Brevo health check failed.",
            extra={"error_type": type(exc).__name__},
        )
        return DependencyDiagnostics(
            connected=False,
            status="critical",
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            error=type(exc).__name__,
        )

    return DependencyDiagnostics(
        connected=True,
        status="healthy",
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )


async def get_system_diagnostics(db: AsyncSession) -> AdminDiagnosticsResponse:
    (
        database,
        vector_store,
        supabase_storage,
        redis,
        email,
        cpu_percent,
        memory_usage,
        disk_usage,
    ) = await asyncio.gather(
        _get_database_diagnostics(db),
        _get_vector_store_diagnostics(),
        _get_supabase_storage_diagnostics(),
        _get_redis_diagnostics(),
        _get_email_diagnostics(),
        _get_cpu_usage_percent(),
        asyncio.to_thread(_get_memory_usage),
        asyncio.to_thread(_get_disk_usage),
    )
    process_memory, memory_limit, memory_percent = memory_usage
    disk_path, disk_used, disk_total, disk_percent = disk_usage

    critical = (
        any(
            dependency.status == "critical"
            for dependency in (
                database,
                vector_store,
                supabase_storage,
                redis,
                email,
            )
        )
        or cpu_percent >= 95
        or memory_percent >= 90
        or disk_percent >= 95
    )
    warning = (
        any(
            dependency.status == "warning"
            for dependency in (
                database,
                vector_store,
                supabase_storage,
                redis,
                email,
            )
        )
        or cpu_percent >= 80
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
        disk_path=disk_path,
        database=database,
        vector_store=vector_store,
        supabase_storage=supabase_storage,
        redis=redis,
        email=email,
        active_thread_count=threading.active_count(),
    )


def get_log_tail(limit: int) -> AdminLogTailResponse:
    return AdminLogTailResponse(logs=get_recent_logs(limit=limit))
