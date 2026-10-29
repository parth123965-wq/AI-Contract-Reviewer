from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class PlaybookRule(BaseModel):
    title: str = Field(description="Short name or category of the policy constraint", examples=["Liability Cap"])
    condition: str = Field(description="Explicit standard or requirement that must be satisfied", examples=["Total liability must be capped at 1x annual contract value"])
    severity: Literal["LOW", "MEDIUM", "HIGH"] = Field(default="HIGH", description="Risk penalty severity if the clause violates this rule")


class PlaybookCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100, description="Name of the review playbook", examples=["SaaS Procurement Standard"])
    description: Optional[str] = Field(default=None, max_length=255, description="Brief description of when to apply this playbook")
    rules: List[PlaybookRule] = Field(default_factory=list, description="Array of custom legal and commercial policy rules")
    is_default: bool = Field(default=False, description="Whether to make this the default playbook for this user")


class PlaybookUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=255)
    rules: Optional[List[PlaybookRule]] = None
    is_default: Optional[bool] = None


class PlaybookResponse(BaseModel):
    id: int = Field(description="Unique playbook ID")
    user_id: Optional[int] = Field(default=None, description="Owner user ID (None for system-wide defaults)")
    name: str
    description: Optional[str] = None
    rules: List[PlaybookRule]
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlaybookListResponse(BaseModel):
    playbooks: List[PlaybookResponse]
