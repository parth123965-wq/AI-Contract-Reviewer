from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services.playbook_service import PlaybookService


@pytest.mark.asyncio
async def test_admin_can_delete_global_playbook():
    service = PlaybookService()
    service.repository = AsyncMock()
    service.repository.get_playbook_by_id.return_value = SimpleNamespace(
        id=3,
        user_id=None,
    )
    db = AsyncMock()

    result = await service.delete_playbook(
        db=db,
        playbook_id=3,
        current_user=SimpleNamespace(id=9, is_admin=True),
    )

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
async def test_non_admin_cannot_delete_global_playbook():
    service = PlaybookService()
    service.repository = AsyncMock()
    service.repository.get_playbook_by_id.return_value = SimpleNamespace(
        id=3,
        user_id=None,
    )

    with pytest.raises(HTTPException) as error:
        await service.delete_playbook(
            db=AsyncMock(),
            playbook_id=3,
            current_user=SimpleNamespace(id=9, is_admin=False),
        )

    assert error.value.status_code == 403
    service.repository.delete_playbook.assert_not_awaited()
