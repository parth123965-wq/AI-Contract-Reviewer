from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.schemas.user import UserResponse
from app.schemas.contract import ContractResponse
from app.models.contract import ContractStatus, RiskLevel

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserAdminDetailResponse(UserResponse):
    total_contracts: int = 0
    updated_at: datetime

class AdminUserListResponse(BaseModel):
    total: int
    page: int
    pages: int = 1
    limit: int
    users: List[UserAdminDetailResponse]

class UserStatusUpdate(BaseModel):
    is_active: bool

class UserRoleUpdate(BaseModel):
    is_admin: bool

class ContractAdminDetailResponse(ContractResponse):
    username: Optional[str] = None
    user_email: Optional[str] = None

class AdminContractListResponse(BaseModel):
    total: int
    page: int
    pages: int = 1
    limit: int
    contracts: List[ContractAdminDetailResponse]

class ContractStatusUpdate(BaseModel):
    status: str

class AdminDashboardStats(BaseModel):
    total_users: int
    active_users: int
    admin_users: int
    total_contracts: int
    contracts_by_status: dict
    analyses_by_risk: dict
