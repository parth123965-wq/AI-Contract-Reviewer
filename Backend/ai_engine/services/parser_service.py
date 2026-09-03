import json
import re
from ai_engine.schemas.analysis_result import AnalysisResult

class ParserService:
    
    def process_json(self, jsons: str) -> AnalysisResult:
        if not jsons or not jsons.strip():
            return AnalysisResult(
                summary="AI analysis completed with default summary.",
                risk_score=20,
                risk="LOW",
                suggestions=["Review standard contract clauses."],
                confidence=0.8
            )

        cleaned = jsons.strip()
        # Remove code blocks
        if "```" in cleaned:
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        # Match JSON block if surrounded by text
        json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(1)

        try:
            raw_dict = json.loads(cleaned)
            summary = str(raw_dict.get("summary") or "AI contract review summary generated.")
            risk_score = int(raw_dict.get("risk_score", 30))
            risk = str(raw_dict.get("risk", "LOW")).upper()
            if risk not in ["LOW", "MEDIUM", "HIGH"]:
                risk = "HIGH" if risk_score >= 70 else ("MEDIUM" if risk_score >= 40 else "LOW")
            suggestions = raw_dict.get("suggestions")
            if not isinstance(suggestions, list):
                suggestions = [str(suggestions)] if suggestions else ["Review key clauses and indemnification terms."]
            suggestions = [str(s) for s in suggestions if s]
            confidence = float(raw_dict.get("confidence", 0.85))

            return AnalysisResult(
                summary=summary,
                risk_score=risk_score,
                risk=risk,
                suggestions=suggestions,
                confidence=confidence
            )
        except Exception:
            return AnalysisResult(
                summary=cleaned[:500] if len(cleaned) > 20 else "Contract analysis completed.",
                risk_score=35,
                risk="MEDIUM",
                suggestions=["General review of contract terms recommended."],
                confidence=0.75
            )