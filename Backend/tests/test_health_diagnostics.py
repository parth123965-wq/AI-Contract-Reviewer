import json
import logging
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.logger import get_app_logger
from ai_engine.logger import get_ai_logger
from app.services import health_diagnostics


@pytest.mark.asyncio
async def test_system_diagnostics_reports_resources_and_database(db_session, monkeypatch):
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
        lambda: (200, 2000, 10.0),
    )

    result = await health_diagnostics.get_system_diagnostics(db_session)

    assert result.overall_status == "healthy"
    assert result.database.connected is True
    assert result.database.latency_ms is not None
    assert result.process_memory_bytes == 100
    assert result.memory_limit_bytes == 1000
    assert result.disk_used_bytes == 200
    assert result.active_thread_count > 0
    assert result.uptime_seconds >= 0


@pytest.mark.asyncio
async def test_system_diagnostics_marks_database_failure_critical(
    db_session, monkeypatch
):
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
        lambda: (200, 2000, 10.0),
    )

    result = await health_diagnostics.get_system_diagnostics(db_session)

    assert result.overall_status == "critical"
    assert result.database.connected is False
    assert result.database.status == "critical"
    assert result.database.error == "SQLAlchemyError"


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
