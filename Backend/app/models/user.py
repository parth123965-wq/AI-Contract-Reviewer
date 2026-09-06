from sqlalchemy import Boolean, String, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.database.database import Base

class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        Index("ix_users_is_admin_is_verified", "is_admin", "is_verified"),
        Index("ix_users_created_at", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True,autoincrement=True)
    username: Mapped[str] = mapped_column(String(100),nullable=False,unique=True,index=True)
    email: Mapped[str] = mapped_column(String(255),nullable=False,unique=True,index=True)
    password_hash: Mapped[str] = mapped_column(String(255),nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean,default=True,nullable=False,index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean,default=False,nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean,default=False,server_default=func.false(),nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),onupdate=func.now(),server_default=func.now())
    contracts = relationship(
        "Contract",
        back_populates='user',
        cascade='all, delete-orphan'
    )