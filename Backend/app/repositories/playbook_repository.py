from typing import Optional, List
from sqlalchemy import select, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.playbook import Playbook


class PlaybookRepository:

    async def create_playbook(self, db: AsyncSession, playbook: Playbook) -> Playbook:
        db.add(playbook)
        await db.commit()
        await db.refresh(playbook)
        return playbook

    async def get_playbook_by_id(
        self,
        db: AsyncSession,
        playbook_id: int,
        user_id: Optional[int] = None
    ) -> Optional[Playbook]:
        query = select(Playbook).where(Playbook.id == playbook_id)
        if user_id is not None:
            # Can access own playbook or global playbook (user_id is NULL)
            query = query.where(or_(Playbook.user_id == user_id, Playbook.user_id.is_(None)))
        result = await db.execute(query)
        return result.scalars().first()

    async def get_user_playbooks(
        self,
        db: AsyncSession,
        user_id: int
    ) -> List[Playbook]:
        query = select(Playbook).where(
            or_(Playbook.user_id == user_id, Playbook.user_id.is_(None))
        ).order_by(Playbook.is_default.desc(), Playbook.id.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_playbook(
        self,
        db: AsyncSession,
        playbook: Playbook,
        commit: bool = True
    ) -> Playbook:
        if commit:
            await db.commit()
            await db.refresh(playbook)
        else:
            await db.flush()
        return playbook

    async def delete_playbook(
        self,
        db: AsyncSession,
        playbook_id: int,
        user_id: int
    ) -> bool:
        stmt = delete(Playbook).where(Playbook.id == playbook_id, Playbook.user_id == user_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
