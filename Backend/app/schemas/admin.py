from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.schemas.user import UserResponse
from app.schemas.contract import ContractResponse
from app.models.contract import ContractStatus, RiskLevel

class AdminLoginRequest(BaseModel):
    email: EmailStr = Field(description="Admin user email address", examples=["admin@example.com"])
    password: str = Field(min_length=8, max_length=128, description="Admin password", examples=["AdminSecret123!"])

class UserAdminDetailResponse(UserResponse):
    total_contracts: int = Field(default=0, description="Total contracts uploaded by this user", examples=[5])
    updated_at: datetime = Field(description="User record last updated timestamp")

class AdminUserListResponse(BaseModel):
    total: int = Field(description="Total count of users matching search query", examples=[42])
    page: int = Field(description="Current pagination page number", examples=[1])
    pages: int = Field(default=1, description="Total available pages", examples=[5])
    limit: int = Field(description="User items per page limit", examples=[10])
    users: List[UserAdminDetailResponse] = Field(description="List of detailed user records")

class UserStatusUpdate(BaseModel):
    is_active: bool = Field(description="Set active (True) or suspended (False) state for user", examples=[True])

class UserRoleUpdate(BaseModel):
    is_admin: bool = Field(description="Grant (True) or revoke (False) admin administrative role", examples=[True])

class ContractAdminDetailResponse(ContractResponse):
    username: Optional[str] = Field(default=None, description="Username of uploading user", examples=["john_doe"])
    user_email: Optional[str] = Field(default=None, description="Email of uploading user", examples=["john@example.com"])

class AdminContractListResponse(BaseModel):
    total: int = Field(description="Total contracts count", examples=[150])
    page: int = Field(description="Current page number", examples=[1])
    pages: int = Field(default=1, description="Total pages count", examples=[15])
    limit: int = Field(description="Items per page limit", examples=[10])
    contracts: List[ContractAdminDetailResponse] = Field(description="List of admin contract records")

class ContractStatusUpdate(BaseModel):
    status: str = Field(description="Update contract status (e.g. processing, completed, error)", examples=["completed"])

class AdminDashboardStats(BaseModel):
    total_users: int = Field(description="Total registered platform users count", examples=[120])
    active_users: int = Field(description="Active user count", examples=[115])
    admin_users: int = Field(description="Administrator count", examples=[3])
    total_contracts: int = Field(description="Total contracts uploaded count", examples=[450])
    contracts_by_status: dict = Field(description="Breakdown of contracts by status string", examples=[{"completed": 400, "processing": 40, "error": 10}])
    analyses_by_risk: dict = Field(description="Breakdown of contract analyses by risk tier", examples=[{"low": 200, "medium": 180, "high": 50, "critical": 20}])

