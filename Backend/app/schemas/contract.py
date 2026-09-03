from pydantic import BaseModel, ConfigDict, computed_field
from app.models.contract import ContractStatus, RiskLevel
from datetime import datetime
from typing import List, Optional, Any

class ContractAnalysisResponse(BaseModel):
    id: int
    contract_id: int
    summary: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[RiskLevel] = None
    recommendations: Optional[str] = None
    high_risk_clause: Optional[Any] = None
    model_name: Optional[str] = None
    confidence_score: Optional[float] = None
    processing_time_ms: Optional[int] = None
    analysis_version: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True
    )

class ContractResponse(BaseModel):
    id: int
    original_filename: str
    file_size: int
    content_type: str
    status: ContractStatus
    created_at: datetime
    analyses: List[ContractAnalysisResponse] = []

    @computed_field
    @property
    def latest_analysis(self) -> Optional[ContractAnalysisResponse]:
        if self.analyses:
            return self.analyses[-1]
        return None

    @computed_field
    @property
    def summary(self) -> Optional[str]:
        return self.latest_analysis.summary if self.latest_analysis else None

    @computed_field
    @property
    def risk_score(self) -> Optional[int]:
        return self.latest_analysis.risk_score if self.latest_analysis else None

    @computed_field
    @property
    def risk_level(self) -> Optional[str]:
        return self.latest_analysis.risk_level.value if self.latest_analysis and self.latest_analysis.risk_level else None

    @computed_field
    @property
    def key_findings(self) -> List[dict]:
        if not self.latest_analysis or not self.latest_analysis.recommendations:
            return []
        recs = [r.strip() for r in self.latest_analysis.recommendations.split("\n") if r.strip()]
        return [{"type": (self.risk_level.lower() if self.risk_level else "medium"), "clause": f"Recommendation #{idx+1}", "description": rec} for idx, rec in enumerate(recs)]

    model_config = ConfigDict(
        from_attributes=True
    )

class ContractListResponse(BaseModel):
    contracts: List[ContractResponse]