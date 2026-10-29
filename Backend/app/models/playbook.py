from datetime import datetime
from typing import Optional, Any
from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Integer,
    Boolean,
    JSON,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.database import Base


class Playbook(Base):
    __tablename__ = "playbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rules: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="playbooks", lazy="selectin")

    __table_args__ = (
        Index("ix_playbooks_user_id_is_default", "user_id", "is_default"),
    )
