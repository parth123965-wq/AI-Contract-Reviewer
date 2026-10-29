from typing import List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.playbook import Playbook
from app.models.user import User
from app.schemas.playbook import PlaybookCreate, PlaybookUpdate
from app.repositories.playbook_repository import PlaybookRepository


class PlaybookService:

    def __init__(self):
        self.repository = PlaybookRepository()

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
        
        # Protect global playbooks from non-admin modification
        if playbook.user_id is None and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators may modify global playbooks."
            )

        if data.name is not None:
            playbook.name = data.name.strip()
        if data.description is not None:
            playbook.description = data.description.strip() if data.description else None
        if data.rules is not None:
            playbook.rules = [r.model_dump() for r in data.rules]
        if data.is_default is not None:
            playbook.is_default = data.is_default

        return await self.repository.update_playbook(db=db, playbook=playbook)

    async def delete_playbook(
        self,
        db: AsyncSession,
        playbook_id: int,
        current_user: User
    ) -> dict:
        playbook = await self.get_playbook(db=db, playbook_id=playbook_id, current_user=current_user)
        if playbook.user_id is None and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Global playbooks cannot be deleted."
            )
        deleted = await self.repository.delete_playbook(
            db=db,
            playbook_id=playbook_id,
            user_id=playbook.user_id or current_user.id
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playbook not found."
            )
        return {"message": "Playbook deleted successfully", "playbook_id": playbook_id}


def get_playbook_service() -> PlaybookService:
    return PlaybookService()
