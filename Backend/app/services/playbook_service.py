from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.playbook import Playbook
from app.models.user import User
from app.schemas.playbook import PlaybookCreate, PlaybookUpdate
from app.repositories.playbook_repository import PlaybookRepository
from app.repositories.user_repository import UserRepository


class PlaybookService:

    def __init__(self):
        self.repository = PlaybookRepository()
        self.user_repository = UserRepository()

    def _apply_update(self, playbook: Playbook, data: PlaybookUpdate) -> None:
        if data.name is not None:
            playbook.name = data.name.strip()
        if data.description is not None:
            playbook.description = data.description.strip() if data.description else None
        if data.rules is not None:
            playbook.rules = [r.model_dump() for r in data.rules]
        if data.is_default is not None:
            playbook.is_default = data.is_default

    async def create_playbook(
        self,
        db: AsyncSession,
        current_user: User,
        data: PlaybookCreate
    ) -> Playbook:
        rules_dump = [r.model_dump() for r in data.rules]
        playbook = Playbook(
            user_id=current_user.id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            rules=rules_dump,
            is_default=data.is_default
        )
        return await self.repository.create_playbook(db=db, playbook=playbook)

    async def create_admin_playbook(
        self,
        db: AsyncSession,
        data: PlaybookCreate,
        user_id: Optional[int] = None,
    ) -> Playbook:
        if user_id is not None:
            user = await self.user_repository.get_user_by_id(
                db=db,
                user_id=user_id,
            )
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Playbook owner user not found.",
                )
        playbook = Playbook(
            user_id=user_id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            rules=[rule.model_dump() for rule in data.rules],
            is_default=data.is_default,
        )
        return await self.repository.create_playbook(db=db, playbook=playbook)

    async def get_admin_playbooks(
        self,
        db: AsyncSession,
        user_id: Optional[int] = None,
    ) -> List[Playbook]:
        return await self.repository.get_all_playbooks(db=db, user_id=user_id)

    async def get_admin_playbook(
        self,
        db: AsyncSession,
        playbook_id: int,
    ) -> Playbook:
        playbook = await self.repository.get_playbook_by_id(
            db=db,
            playbook_id=playbook_id,
        )
        if playbook is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playbook not found.",
            )
        return playbook

    async def get_user_playbooks(
        self,
        db: AsyncSession,
        current_user: User
    ) -> List[Playbook]:
        return await self.repository.get_user_playbooks(db=db, user_id=current_user.id)

    async def get_playbook(
        self,
        db: AsyncSession,
        playbook_id: int,
        current_user: User
    ) -> Playbook:
        playbook = await self.repository.get_playbook_by_id(
            db=db,
            playbook_id=playbook_id,
            user_id=current_user.id
        )
        if not playbook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playbook not found or access denied."
            )
        return playbook

    async def update_playbook(
        self,
        db: AsyncSession,
        playbook_id: int,
        current_user: User,
        data: PlaybookUpdate
    ) -> Playbook:
        playbook = await self.get_playbook(db=db, playbook_id=playbook_id, current_user=current_user)
        if playbook.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the playbook owner may modify this playbook."
            )

        self._apply_update(playbook, data)
        return await self.repository.update_playbook(db=db, playbook=playbook)

    async def update_admin_playbook(
        self,
        db: AsyncSession,
        playbook_id: int,
        data: PlaybookUpdate,
    ) -> Playbook:
        playbook = await self.get_admin_playbook(db=db, playbook_id=playbook_id)
        self._apply_update(playbook, data)
        return await self.repository.update_playbook(db=db, playbook=playbook)

    async def delete_playbook(
        self,
        db: AsyncSession,
        playbook_id: int,
        current_user: User
    ) -> dict:
        playbook = await self.get_playbook(db=db, playbook_id=playbook_id, current_user=current_user)
        if playbook.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the playbook owner may delete this playbook."
            )
        deleted = await self.repository.delete_playbook(
            db=db,
            playbook_id=playbook_id,
            user_id=current_user.id
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playbook not found."
            )
        return {"message": "Playbook deleted successfully", "playbook_id": playbook_id}

    async def delete_admin_playbook(
        self,
        db: AsyncSession,
        playbook_id: int,
    ) -> dict:
        playbook = await self.get_admin_playbook(db=db, playbook_id=playbook_id)
        deleted = await self.repository.delete_playbook(
            db=db,
            playbook_id=playbook_id,
            user_id=playbook.user_id,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playbook not found.",
            )
        return {"message": "Playbook deleted successfully", "playbook_id": playbook_id}


def get_playbook_service() -> PlaybookService:
    return PlaybookService()
