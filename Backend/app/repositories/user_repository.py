from sqlalchemy.orm import Session
from app.models.user import User
from sqlalchemy import select 
from typing import Optional

class UserRepository:
    def create_user(self, db: Session, user: User) -> User:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        statement = select(User).where(User.email == email)
        result = db.execute(statement=statement).scalar_one_or_none()
        return result
        
    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        statement = select(User).where(User.id == user_id)
        result = db.execute(statement=statement).scalar_one_or_none()
        return result

    def get_all_users(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> list[User]:
        from sqlalchemy import or_
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
        return list(db.execute(statement).scalars().all())

    def count_users(
        self,
        db: Session,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> int:
        from sqlalchemy import func, or_
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
        return db.execute(statement).scalar() or 0

    def update_user_status(self, db: Session, user_id: int, is_active: bool) -> Optional[User]:
        user = self.get_user_by_id(db=db, user_id=user_id)
        if user:
            user.is_active = is_active
            db.commit()
            db.refresh(user)
        return user

    def update_user_role(self, db: Session, user_id: int, is_admin: bool) -> Optional[User]:
        user = self.get_user_by_id(db=db, user_id=user_id)
        if user:
            user.is_admin = is_admin
            db.commit()
            db.refresh(user)
        return user

    def delete_user(self, db: Session, user_id: int) -> bool:
        user = self.get_user_by_id(db=db, user_id=user_id)
        if user:
            db.delete(user)
            db.commit()
            return True
        return False