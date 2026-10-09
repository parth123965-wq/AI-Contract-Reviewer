import json
import logging
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.logger import get_app_logger
from app.schemas.admin import DependencyDiagnostics
from ai_engine.logger import get_ai_logger
from app.services import health_diagnostics


def mock_external_checks(monkeypatch, *, vector_store=None):
    healthy = DependencyDiagnostics(
        connected=True,
        status="healthy",
        latency_ms=1.0,
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_vector_store_diagnostics",
        AsyncMock(return_value=vector_store or healthy),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_supabase_storage_diagnostics",
        AsyncMock(return_value=healthy),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_redis_diagnostics",
        AsyncMock(return_value=healthy),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_email_diagnostics",
        AsyncMock(return_value=healthy),
    )


@pytest.mark.asyncio
async def test_system_diagnostics_reports_resources_and_database(db_session, monkeypatch):
    mock_external_checks(monkeypatch)
    monkeypatch.setattr(
        health_diagnostics,
        "_get_cpu_usage_percent",
        AsyncMock(return_value=25.0),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_memory_usage",
        lambda: (100, 1000, 10.0),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_disk_usage",
        lambda: ("/var/data", 200, 2000, 10.0),
    )

    result = await health_diagnostics.get_system_diagnostics(db_session)

    assert result.overall_status == "healthy"
    assert result.database.connected is True
    assert result.database.latency_ms is not None
    assert result.process_memory_bytes == 100
    assert result.memory_limit_bytes == 1000
    assert result.disk_used_bytes == 200
    assert result.disk_path == "/var/data"
    assert result.vector_store.connected is True
    assert result.supabase_storage.connected is True
    assert result.redis.connected is True
    assert result.email.connected is True
    assert result.active_thread_count > 0
    assert result.uptime_seconds >= 0


@pytest.mark.asyncio
async def test_system_diagnostics_marks_database_failure_critical(
    db_session, monkeypatch
):
    mock_external_checks(monkeypatch)
    monkeypatch.setattr(
        db_session,
        "execute",
        AsyncMock(side_effect=SQLAlchemyError("database unavailable")),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_cpu_usage_percent",
        AsyncMock(return_value=0.0),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_memory_usage",
        lambda: (100, 1000, 10.0),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_disk_usage",
        lambda: ("/var/data", 200, 2000, 10.0),
    )

    result = await health_diagnostics.get_system_diagnostics(db_session)

    assert result.overall_status == "critical"
    assert result.database.connected is False
    assert result.database.status == "critical"
    assert result.database.error == "SQLAlchemyError"


@pytest.mark.asyncio
async def test_external_dependency_failure_makes_overall_status_critical(
    db_session, monkeypatch
):
    mock_external_checks(
        monkeypatch,
        vector_store=DependencyDiagnostics(
            connected=False,
            status="critical",
            latency_ms=1.0,
            error="LookupError",
        ),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_cpu_usage_percent",
        AsyncMock(return_value=0.0),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_memory_usage",
        lambda: (100, 1000, 10.0),
    )
    monkeypatch.setattr(
        health_diagnostics,
        "_get_disk_usage",
        lambda: ("/var/data", 200, 2000, 10.0),
    )

    result = await health_diagnostics.get_system_diagnostics(db_session)

    assert result.vector_store.connected is False
    assert result.vector_store.error == "LookupError"
    assert result.overall_status == "critical"


@pytest.mark.asyncio
async def test_redis_health_check_pings_configured_client(monkeypatch):
    redis_client = SimpleNamespace(ping=AsyncMock(return_value=True))
    monkeypatch.setattr(health_diagnostics.redis_setup, "redis_client", redis_client)

    result = await health_diagnostics._get_redis_diagnostics()

    redis_client.ping.assert_awaited_once()
    assert result.connected is True
    assert result.status == "healthy"
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_pinecone_health_check_verifies_configured_index(monkeypatch):
    client = SimpleNamespace(
        list_indexes=lambda: SimpleNamespace(names=lambda: ["contracts"]),
        describe_index=lambda name: SimpleNamespace(status={"ready": True}),
    )
    monkeypatch.setitem(
        sys.modules,
        "pinecone",
        SimpleNamespace(Pinecone=lambda *, api_key: client),
    )
    check_results = []

    async def run_check(checker):
        checker()
        check_results.append(True)
        return DependencyDiagnostics(
            connected=True,
            status="healthy",
            latency_ms=1.0,
        )

    monkeypatch.setattr(
        health_diagnostics, "_run_sync_dependency_check", run_check
    )

    result = await health_diagnostics._get_vector_store_diagnostics()

    assert check_results == [True]
    assert result.connected is True


@pytest.mark.asyncio
async def test_supabase_health_check_verifies_uploads_bucket(monkeypatch):
    storage = SimpleNamespace(
        get_bucket=lambda bucket: (
            {"name": bucket} if bucket == "uploads" else None
        )
    )
    class FakeContractStorage:
        BUCKET_NAME = "uploads"

        def __init__(self):
            self.client = SimpleNamespace(storage=storage)

    monkeypatch.setattr(health_diagnostics, "ContractStorage", FakeContractStorage)

    async def run_check(checker):
        checker()
        return DependencyDiagnostics(
            connected=True,
            status="healthy",
            latency_ms=1.0,
        )

    monkeypatch.setattr(
        health_diagnostics, "_run_sync_dependency_check", run_check
    )

    result = await health_diagnostics._get_supabase_storage_diagnostics()

    assert result.connected is True
    assert result.status == "healthy"


@pytest.mark.asyncio
async def test_brevo_health_check_requires_configured_sender_to_be_active(
    monkeypatch,
):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "senders": [
                    {"email": "sender@gmail.com", "active": True},
                ],
            }

    class FakeAsyncClient:
        def __init__(self, *, timeout):
            assert timeout == 5.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, *, headers):
            assert url == "https://api.brevo.com/v3/senders"
            assert headers["api-key"]
            return FakeResponse()

    monkeypatch.setattr(
        health_diagnostics.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    result = await health_diagnostics._get_email_diagnostics()

    assert result.connected is True
    assert result.status == "healthy"
    assert result.latency_ms is not None


def test_recent_log_endpoint_buffer_contains_structured_app_logs():
    unique_message = "health-diagnostics-log-buffer-test"
    logger = get_app_logger("health_diagnostics_test")
    logger.setLevel(logging.WARNING)
    logger.warning(unique_message)

    entries = [
        json.loads(line)
        for line in health_diagnostics.get_log_tail(limit=50).logs
    ]
    matching = [entry for entry in entries if entry["message"] == unique_message]

    assert matching
    assert matching[-1]["level"] == "WARNING"


def test_recent_log_endpoint_buffer_contains_ai_engine_logs():
    unique_message = "health-diagnostics-ai-log-buffer-test"
    logger = get_ai_logger("health_diagnostics_test")
    logger.setLevel(logging.WARNING)
    logger.warning(unique_message)

    entries = [
        json.loads(line)
        for line in health_diagnostics.get_log_tail(limit=50).logs
    ]
    matching = [entry for entry in entries if entry["message"] == unique_message]

    assert matching
    assert matching[-1]["service"] == "ai_engine"


def test_container_resource_limits_use_linux_cgroup_values(monkeypatch):
    cgroup_values = {
        "/sys/fs/cgroup/memory.max": "536870912",
        "/sys/fs/cgroup/cpu.max": "50000 100000",
    }
    monkeypatch.setattr(
        health_diagnostics,
        "_read_cgroup_value",
        lambda path: cgroup_values.get(path),
    )

    assert health_diagnostics._get_memory_limit_bytes() == 536870912
    assert health_diagnostics._get_cpu_quota_cores() == 0.5


def test_disk_diagnostics_uses_render_persistent_mount(monkeypatch):
    disk_usage = SimpleNamespace(used=100, total=1000, percent=10.0)
    render_disk = health_diagnostics.Path("/var/data")
    monkeypatch.setattr(
        health_diagnostics.Path,
        "exists",
        lambda self: self.as_posix() == "/var/data",
    )
    monkeypatch.setattr(
        os.path, "ismount", lambda path: health_diagnostics.Path(path).as_posix() == "/var/data"
    )
    monkeypatch.setattr(
        health_diagnostics.psutil,
        "disk_usage",
        lambda path: disk_usage,
    )

    result = health_diagnostics._get_disk_usage()

    assert result == (str(render_disk), 100, 1000, 10.0)


def test_admin_diagnostics_routes_are_rate_limited_and_typed():
    from app.api.admin import admin_router
    from app.core.rate_limit import RateLimiter
    from app.dependencies.auth import get_current_admin
    from app.schemas.admin import AdminDiagnosticsResponse, AdminLogTailResponse

    expected = {
        "/admin/diagnostics": AdminDiagnosticsResponse,
        "/admin/diagnostics/logs": AdminLogTailResponse,
    }
    routes = {
        route.path: route
        for route in admin_router.routes
        if route.path in expected
    }

    assert set(routes) == set(expected)
    for path, response_model in expected.items():
        route = routes[path]
        assert route.response_model is response_model
        assert any(
            isinstance(dependency.call, RateLimiter)
            for dependency in route.dependant.dependencies
        )
        assert any(
            dependency.call is get_current_admin
            for dependency in route.dependant.dependencies
        )


def test_diagnostics_endpoints_are_in_openapi_with_typed_responses():
    from app.main import app

    paths = app.openapi()["paths"]

    assert (
        paths["/admin/diagnostics"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/AdminDiagnosticsResponse"
    )
    assert (
        paths["/admin/diagnostics/logs"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/AdminLogTailResponse"
    )
