from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.playbook import (
    PlaybookCreate,
    PlaybookUpdate,
    PlaybookResponse,
    PlaybookListResponse
)
from app.services.playbook_service import PlaybookService, get_playbook_service
from app.core.rate_limit import RateLimiter

playbook_router = APIRouter(
    prefix="/playbooks",
    tags=["Review Playbooks"]
)


@playbook_router.post(
    "",
    response_model=PlaybookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Custom Review Playbook",
    description="Define a custom organizational review policy with explicit risk criteria.",
    dependencies=[Depends(RateLimiter(times=15, seconds=60, prefix="playbooks_create"))]
)
async def create_playbook(
    body: PlaybookCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PlaybookService, Depends(get_playbook_service)]
) -> PlaybookResponse:
    playbook = await service.create_playbook(db=db, current_user=current_user, data=body)
    return PlaybookResponse.model_validate(playbook)


@playbook_router.get(
    "",
    response_model=PlaybookListResponse,
    summary="List Review Playbooks",
    description="Retrieve all playbooks available to the current user (including global templates).",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="playbooks_list"))]
)
async def list_playbooks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PlaybookService, Depends(get_playbook_service)]
) -> PlaybookListResponse:
    playbooks = await service.get_user_playbooks(db=db, current_user=current_user)
    return PlaybookListResponse(playbooks=[PlaybookResponse.model_validate(p) for p in playbooks])


@playbook_router.get(
    "/{playbook_id}",
    response_model=PlaybookResponse,
    summary="Get Playbook Details",
    description="Retrieve specific playbook rules by ID.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="playbooks_get"))]
)
async def get_playbook(
    playbook_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PlaybookService, Depends(get_playbook_service)]
) -> PlaybookResponse:
    playbook = await service.get_playbook(db=db, playbook_id=playbook_id, current_user=current_user)
    return PlaybookResponse.model_validate(playbook)


@playbook_router.patch(
    "/{playbook_id}",
    response_model=PlaybookResponse,
    summary="Update Review Playbook",
    description="Modify an existing review playbook and its policy rules.",
    dependencies=[Depends(RateLimiter(times=15, seconds=60, prefix="playbooks_update"))]
)
async def update_playbook(
    playbook_id: int,
    body: PlaybookUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PlaybookService, Depends(get_playbook_service)]
) -> PlaybookResponse:
    playbook = await service.update_playbook(db=db, playbook_id=playbook_id, current_user=current_user, data=body)
    return PlaybookResponse.model_validate(playbook)


@playbook_router.delete(
    "/{playbook_id}",
    summary="Delete Review Playbook",
    description="Delete a custom review playbook.",
    dependencies=[Depends(RateLimiter(times=15, seconds=60, prefix="playbooks_delete"))]
)
async def delete_playbook(
    playbook_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PlaybookService, Depends(get_playbook_service)]
):
    return await service.delete_playbook(db=db, playbook_id=playbook_id, current_user=current_user)
