from unittest.mock import AsyncMock

import pytest

from app.services.admin_service import AdminService


@pytest.mark.asyncio
async def test_dashboard_queries_run_sequentially_on_shared_session():
    service = AdminService()
    events = []

    async def user_stats(**kwargs):
        events.append("users")
        return {"total_users": 10, "active_users": 8, "admin_users": 2}

    async def total_contracts(**kwargs):
        events.append("contracts")
        return 7

    async def contracts_by_status(**kwargs):
        events.append("status")
        return {"COMPLETED": 7}

    async def analyses_by_risk(**kwargs):
        events.append("risk")
        return {"LOW": 3}

    service.user_repository = AsyncMock()
    service.contract_repository = AsyncMock()
    service.user_repository.get_user_summary_stats.side_effect = user_stats
    service.contract_repository.count_all_contracts.side_effect = total_contracts
    service.contract_repository.count_contracts_by_status.side_effect = contracts_by_status
    service.contract_repository.count_analyses_by_risk.side_effect = analyses_by_risk
    db = object()

    result = await service.get_dashboard_stats(db)

    assert events == ["users", "contracts", "status", "risk"]
    assert result.total_users == 10
    assert result.total_contracts == 7
    assert result.contracts_by_status == {"COMPLETED": 7}
    assert result.analyses_by_risk == {"LOW": 3}
