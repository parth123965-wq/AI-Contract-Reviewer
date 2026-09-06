from pydantic import BaseModel, ConfigDict, Field, computed_field
from app.models.contract import ContractStatus, RiskLevel
from datetime import datetime
from typing import List, Optional, Any

class ContractAnalysisResponse(BaseModel):
    id: int = Field(description="Unique analysis record ID", examples=[1])
    contract_id: int = Field(description="Associated contract file ID", examples=[10])
    summary: Optional[str] = Field(default=None, description="AI-generated executive summary of the contract", examples=["Standard NDA with 2-year confidentiality duration."])
    risk_score: Optional[int] = Field(default=None, description="Calculated risk score from 0 to 100", examples=[35])
    risk_level: Optional[RiskLevel] = Field(default=None, description="Categorized risk tier (low, medium, high, critical)")
    recommendations: Optional[str] = Field(default=None, description="AI recommendations for clause modification")
    high_risk_clause: Optional[Any] = Field(default=None, description="Identified high risk clauses or exposure terms")
    model_name: Optional[str] = Field(default=None, description="AI model engine used for analysis", examples=["gemini-1.5-flash"])
    confidence_score: Optional[float] = Field(default=None, description="Model confidence score between 0.0 and 1.0", examples=[0.94])
    processing_time_ms: Optional[int] = Field(default=None, description="Analysis execution latency in milliseconds", examples=[1450])
    analysis_version: Optional[int] = Field(default=None, description="Pipeline analysis schema version", examples=[1])
    created_at: Optional[datetime] = Field(default=None, description="Analysis completion timestamp")

    model_config = ConfigDict(
        from_attributes=True
    )

class ContractResponse(BaseModel):
    id: int = Field(description="Unique contract ID", examples=[10])
    original_filename: str = Field(description="Original uploaded document filename", examples=["Software_Services_Agreement.pdf"])
    file_size: int = Field(description="File size in bytes", examples=[204800])
    content_type: str = Field(description="MIME content type", examples=["application/pdf"])
    status: ContractStatus = Field(description="Current processing status (processing, completed, error)")
    created_at: datetime = Field(description="Document upload timestamp")
    analyses: List[ContractAnalysisResponse] = Field(default=[], description="Historical analysis runs for this document")

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
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 10,
                "original_filename": "Software_Services_Agreement.pdf",
                "file_size": 204800,
                "content_type": "application/pdf",
                "status": "completed",
                "created_at": "2026-09-06T12:00:00Z",
                "summary": "Standard Software Services Agreement with indemnification terms.",
                "risk_score": 35,
                "risk_level": "medium",
                "key_findings": [
                    {
                        "type": "medium",
                        "clause": "Recommendation #1",
                        "description": "Specify explicit limitation of liability cap."
                    }
                ]
            }
        }
    )

class ContractListResponse(BaseModel):
    contracts: List[ContractResponse] = Field(description="Array of user contracts")

class QuestionRequest(BaseModel):
    question: str = Field(
        min_length=3,
        max_length=1000,
        description="Natural language question regarding the contract clauses",
        examples=["What is the termination notice period required in clause 8?"]
    )