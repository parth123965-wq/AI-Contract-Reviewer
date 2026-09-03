from pydantic import BaseModel
from typing import Optional


class AnalysisResult(BaseModel):
    summary: str
    risk_score: int
    risk: str
    suggestions: list[str]
    confidence: float
    error: Optional[str] = None
    prompt: Optional[str] = None
    llm_response: Optional[str] = None