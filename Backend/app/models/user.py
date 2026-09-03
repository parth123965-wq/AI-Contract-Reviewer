from sqlalchemy import Boolean , String , DateTime , func 
from sqlalchemy.orm import Mapped , mapped_column , relationship
from datetime import datetime
from app.database.database import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True,autoincrement=True)
    username: Mapped[str] = mapped_column(String(100),nullable=False)
    email: Mapped[str] = mapped_column(String(255),nullable=False,unique=True,index=True)
    password_hash: Mapped[str] = mapped_column(String(255),nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean,default=True,nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean,default=False,nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),onupdate=func.now(),server_default=func.now())
    contracts = relationship(
        "Contract",
        back_populates='user',
        cascade='all, delete-orphan'
    )