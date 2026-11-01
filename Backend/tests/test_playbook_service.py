from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.admin import admin_router
from app.core.rate_limit import RateLimiter
from app.dependencies.auth import get_current_admin
from app.schemas.playbook import (
    AdminPlaybookCreate,
    PlaybookCreate,
    PlaybookRule,
    PlaybookUpdate,
)
from app.services.playbook_service import PlaybookService


@pytest.mark.asyncio
async def test_admin_can_create_global_playbook():
    service = PlaybookService()
    service.repository = AsyncMock()
    service.user_repository = AsyncMock()
    db = AsyncMock()
    data = AdminPlaybookCreate(
        name="  Global Standard  ",
        description="  Shared review rules  ",
        rules=[
            PlaybookRule(
                title="Liability",
                condition="Cap liability at annual fees",
            )
        ],
    )

    await service.create_admin_playbook(db=db, data=data, user_id=data.user_id)

    created = service.repository.create_playbook.await_args.kwargs["playbook"]
    assert created.user_id is None
    assert created.name == "Global Standard"
    assert created.description == "Shared review rules"
    assert len(created.rules) == 1


@pytest.mark.asyncio
async def test_admin_can_create_playbook_for_specific_user():
    service = PlaybookService()
    service.repository = AsyncMock()
    service.user_repository = AsyncMock()
    service.user_repository.get_user_by_id.return_value = SimpleNamespace(id=27)
    db = AsyncMock()
    data = AdminPlaybookCreate(name="Assigned policy", user_id=27)

    await service.create_admin_playbook(db=db, data=data, user_id=data.user_id)

    created = service.repository.create_playbook.await_args.kwargs["playbook"]
    assert created.user_id == 27
    service.user_repository.get_user_by_id.assert_awaited_once_with(
        db=db,
        user_id=27,
    )


@pytest.mark.asyncio
async def test_admin_list_can_show_all_or_filter_to_user_playbooks():
    service = PlaybookService()
    service.repository = AsyncMock()
    service.repository.get_all_playbooks.return_value = ["global", "owned"]
    db = AsyncMock()

    all_playbooks = await service.get_admin_playbooks(db=db)
    user_playbooks = await service.get_admin_playbooks(db=db, user_id=27)

    assert all_playbooks == ["global", "owned"]
    assert user_playbooks == ["global", "owned"]
    assert service.repository.get_all_playbooks.await_args_list[0].kwargs == {
        "db": db,
        "user_id": None,
    }
    assert service.repository.get_all_playbooks.await_args_list[1].kwargs == {
        "db": db,
        "user_id": 27,
    }


@pytest.mark.asyncio
async def test_admin_can_read_any_playbook():
    service = PlaybookService()
    service.repository = AsyncMock()
    playbook = SimpleNamespace(id=3, user_id=27)
    service.repository.get_playbook_by_id.return_value = playbook

    result = await service.get_admin_playbook(db=AsyncMock(), playbook_id=3)

    assert result is playbook
    service.repository.get_playbook_by_id.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_cannot_create_playbook_for_nonexistent_user():
    service = PlaybookService()
    service.repository = AsyncMock()
    service.user_repository = AsyncMock()
    service.user_repository.get_user_by_id.return_value = None

    with pytest.raises(HTTPException) as error:
        await service.create_admin_playbook(
            db=AsyncMock(),
            data=AdminPlaybookCreate(name="Assigned policy", user_id=27),
            user_id=27,
        )

    assert error.value.status_code == 404
    service.repository.create_playbook.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_can_update_global_playbook():
    service = PlaybookService()
    service.repository = AsyncMock()
    db = AsyncMock()
    playbook = SimpleNamespace(
        id=3,
        user_id=None,
        name="Old name",
        description=None,
        rules=[],
        is_default=False,
    )
    service.repository.get_playbook_by_id.return_value = playbook
    service.repository.update_playbook.side_effect = (
        lambda *, db, playbook: playbook
    )

    result = await service.update_admin_playbook(
        db=db,
        playbook_id=3,
        data=PlaybookUpdate(name="New name", is_default=True),
    )

    assert result.name == "New name"
    assert result.is_default is True
    service.repository.update_playbook.assert_awaited_once_with(
        db=db,
        playbook=playbook,
    )


@pytest.mark.asyncio
async def test_admin_can_delete_global_playbook():
    service = PlaybookService()
    service.repository = AsyncMock()
    service.repository.get_playbook_by_id.return_value = SimpleNamespace(
        id=3,
        user_id=None,
    )
    db = AsyncMock()

    result = await service.delete_admin_playbook(db=db, playbook_id=3)

    assert result == {
        "message": "Playbook deleted successfully",
        "playbook_id": 3,
    }
    service.repository.delete_playbook.assert_awaited_once_with(
        db=db,
        playbook_id=3,
        user_id=None,
    )


@pytest.mark.asyncio
async def test_admin_can_manage_user_owned_playbooks():
    service = PlaybookService()
    service.repository = AsyncMock()
    playbook = SimpleNamespace(
        id=3,
        user_id=9,
        name="Old name",
        description=None,
        rules=[],
        is_default=False,
    )
    service.repository.get_playbook_by_id.return_value = playbook
    service.repository.update_playbook.side_effect = (
        lambda *, db, playbook: playbook
    )

    updated = await service.update_admin_playbook(
        db=AsyncMock(),
        playbook_id=3,
        data=PlaybookUpdate(name="Changed"),
    )
    deleted = await service.delete_admin_playbook(db=AsyncMock(), playbook_id=3)

    assert updated.name == "Changed"
    assert deleted["playbook_id"] == 3
    service.repository.update_playbook.assert_awaited_once()
    service.repository.delete_playbook.assert_awaited_once_with(
        db=service.repository.delete_playbook.await_args.kwargs["db"],
        playbook_id=3,
        user_id=9,
    )


@pytest.mark.asyncio
async def test_admin_cannot_change_global_playbook_through_personal_route():
    service = PlaybookService()
    service.repository = AsyncMock()
    service.repository.get_playbook_by_id.return_value = SimpleNamespace(
        id=3,
        user_id=None,
    )

    with pytest.raises(HTTPException) as update_error:
        await service.update_playbook(
            db=AsyncMock(),
            playbook_id=3,
            current_user=SimpleNamespace(id=9, is_admin=True),
            data=PlaybookUpdate(name="Changed"),
        )
    with pytest.raises(HTTPException) as delete_error:
        await service.delete_playbook(
            db=AsyncMock(),
            playbook_id=3,
            current_user=SimpleNamespace(id=9, is_admin=True),
        )

    assert update_error.value.status_code == 403
    assert delete_error.value.status_code == 403
    service.repository.delete_playbook.assert_not_awaited()
    service.repository.update_playbook.assert_not_awaited()


def test_global_playbook_admin_routes_require_admin_and_are_rate_limited():
    expected_paths = {
        "/admin/playbooks",
        "/admin/playbooks/{playbook_id}",
    }
    routes = [
        route
        for route in admin_router.routes
        if route.path in expected_paths
    ]

    assert {route.path for route in routes} == expected_paths
    assert {method for route in routes for method in route.methods} == {
        "POST",
        "GET",
        "PATCH",
        "DELETE",
    }
    for route in routes:
        assert any(
            dependency.call is get_current_admin
            for dependency in route.dependant.dependencies
        )
        assert any(
            isinstance(dependency.call, RateLimiter)
            for dependency in route.dependant.dependencies
        )
