from datetime import datetime
from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Integer,
    BigInteger,
    Float,
    Boolean,
    Enum as SQLEnum,
    func,
    Text,
    JSON,
    TIMESTAMP
)
from enum import Enum
from sqlalchemy.orm import Mapped , mapped_column , relationship
from app.database.database import Base
from typing import Optional
    
class ContractStatus(str,Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    
class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    
class Contract(Base):
    __tablename__ = "contracts"
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    status: Mapped[ContractStatus] = mapped_column(
        SQLEnum(ContractStatus),
        default=ContractStatus.UPLOADED,
        nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    deleted_at: Mapped[datetime|None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    user = relationship(
        "User",
        back_populates="contracts"
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    analyses = relationship(
        "ContractAnalysis",
        back_populates="contract"
    )
    
class ContractAnalysis(Base):
    __tablename__ = "contract_analyses"
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id"),
        nullable=False,
        index=True
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    risk_score: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SQLEnum(RiskLevel),
        nullable=True
    )
    recommendations: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    high_risk_clause: Mapped[str] = mapped_column(
        JSON,
        nullable=True
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=True
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=True
    )
    processing_time_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )
    analysis_version: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True
    )
    contract = relationship(
        "Contract",
        back_populates="analyses"
    )