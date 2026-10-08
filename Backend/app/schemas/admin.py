from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime
from pydantic import EmailStr
from app.schemas.user import UserResponse
from app.schemas.contract import ContractResponse

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

class AdminEmailChangeRequestResponse(BaseModel):
    message: str = Field(description="Email verification status")
    email: EmailStr = Field(description="Target email address awaiting OTP verification")

class ContractAdminDetailResponse(ContractResponse):
    username: Optional[str] = Field(default=None, description="Username of uploading user", examples=["john_doe"])
    user_email: Optional[str] = Field(default=None, description="Email of uploading user", examples=["john@example.com"])
    is_deleted: bool = Field(description="Whether the contract has been soft-deleted")
    deleted_at: Optional[datetime] = Field(default=None, description="When the contract was soft-deleted")

class AdminContractListResponse(BaseModel):
    total: int = Field(description="Total contracts count", examples=[150])
    page: int = Field(description="Current page number", examples=[1])
    pages: int = Field(default=1, description="Total pages count", examples=[15])
    limit: int = Field(description="Items per page limit", examples=[10])
    contracts: List[ContractAdminDetailResponse] = Field(description="List of admin contract records")

class ContractAdminActionResponse(BaseModel):
    message: str = Field(description="Result of the contract action")
    contract_id: int = Field(description="ID of the contract affected by the action")

class ContractStatusUpdate(BaseModel):
    status: str = Field(description="Update contract status (e.g. processing, completed, error)", examples=["completed"])

class AdminDashboardStats(BaseModel):
    total_users: int = Field(description="Total registered platform users count", examples=[120])
    active_users: int = Field(description="Active user count", examples=[115])
    admin_users: int = Field(description="Administrator count", examples=[3])
    total_contracts: int = Field(
        description="Total uploaded contracts that have not been soft-deleted",
        examples=[450],
    )
    contracts_by_status: dict[str, int] = Field(
        description="Non-deleted contracts grouped by their status",
        examples=[{"COMPLETED": 400, "PROCESSING": 40, "FAILED": 10}],
    )
    analyses_by_risk: dict[str, int] = Field(
        description="Analyses of non-deleted contracts grouped by risk level",
        examples=[{"LOW": 200, "MEDIUM": 180, "HIGH": 50, "UNANALYZED": 20}],
    )


class DatabaseDiagnostics(BaseModel):
    connected: bool
    status: Literal["healthy", "critical"]
    latency_ms: Optional[float]
    error: Optional[str] = None


class AdminDiagnosticsResponse(BaseModel):
    overall_status: Literal["healthy", "warning", "critical"] = Field(
        description=(
            "Critical when the database is down or CPU/memory/disk reach 95%/90%/95%; "
            "warning at CPU/memory/disk 80%/80%/85% or database latency >= 1000 ms."
        )
    )
    uptime_seconds: float
    cpu_percent: float = Field(description="Backend process CPU use relative to its container CPU quota")
    process_memory_bytes: int = Field(description="Resident memory used by this backend process")
    memory_limit_bytes: int = Field(description="Container memory limit when available, otherwise host memory")
    memory_percent: float = Field(description="Backend process memory as a percentage of the memory limit")
    disk_used_bytes: int
    disk_total_bytes: int
    disk_percent: float
    database: DatabaseDiagnostics
    active_thread_count: int


class AdminLogTailResponse(BaseModel):
    logs: List[str] = Field(description="Recent structured JSON log lines from this backend instance")
