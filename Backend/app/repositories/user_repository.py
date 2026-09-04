from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from sqlalchemy import select, or_, func
from typing import Optional

class UserRepository:
    async def create_user(self, db: AsyncSession, user: User) -> User:
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        statement = select(User).where(User.email == email)
        result = (await db.execute(statement=statement)).scalar_one_or_none()
        return result
        
    async def get_user_by_id(self, db: AsyncSession, user_id: int) -> Optional[User]:
        statement = select(User).where(User.id == user_id)
        result = (await db.execute(statement=statement)).scalar_one_or_none()
        return result

    async def get_all_users(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> list[User]:
        statement = select(User)
        if is_active is not None:
            statement = statement.where(User.is_active == is_active)
        if search:
            search_pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    User.username.ilike(search_pattern),
                    User.email.ilike(search_pattern)
                )
            )
        statement = statement.order_by(User.id.desc()).offset(skip).limit(limit)
        result = await db.execute(statement)
        return list(result.scalars().all())

    async def count_users(
        self,
        db: AsyncSession,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> int:
        statement = select(func.count(User.id))
        if is_active is not None:
            statement = statement.where(User.is_active == is_active)
        if search:
            search_pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    User.username.ilike(search_pattern),
                    User.email.ilike(search_pattern)
                )
            )
        result = await db.execute(statement)
        return result.scalar() or 0

    async def update_user_status(self, db: AsyncSession, user_id: int, is_active: bool) -> Optional[User]:
        user = await self.get_user_by_id(db=db, user_id=user_id)
        if user:
            user.is_active = is_active
            await db.commit()
            await db.refresh(user)
        return user

    async def update_user_role(self, db: AsyncSession, user_id: int, is_admin: bool) -> Optional[User]:
        user = await self.get_user_by_id(db=db, user_id=user_id)
        if user:
            user.is_admin = is_admin
            await db.commit()
            await db.refresh(user)
        return user

    async def mark_user_verified(self, db: AsyncSession, user_id: int) -> Optional[User]:
        user = await self.get_user_by_id(db=db, user_id=user_id)
        if user:
            user.is_verified = True
            await db.commit()
            await db.refresh(user)
        return user

    async def delete_user(self, db: AsyncSession, user_id: int) -> bool:
        user = await self.get_user_by_id(db=db, user_id=user_id)
        if user:
            await db.delete(user)
            await db.commit()
            return True
        return False