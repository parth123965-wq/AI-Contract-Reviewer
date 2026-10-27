from datetime import datetime, timezone
from app.models.contract import Contract, ContractAnalysis, ContractStatus, RiskLevel
from app.services.report_export_service import export_service
from ai_engine.services.llm_service import LLMService


def test_export_service_html_generation():
    contract = Contract(
        id=42,
        original_filename="Master_Services_Agreement.pdf",
        status=ContractStatus.COMPLETED,
        created_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
        file_size=102400
    )
    analysis = ContractAnalysis(
        id=1,
        contract_id=42,
        summary="Commercial services agreement with standard confidentiality terms.",
        risk_score=65,
        risk_level=RiskLevel.MEDIUM,
        recommendations="Add 30-day notice for convenience termination.\nCap liability at fees paid.",
        high_risk_clause=["Uncapped indemnification in Section 11."],
        analysis_version=1
    )
    contract.analyses = [analysis]

    # Test HTML generation
    html = export_service.generate_html_report(contract)
    assert "Master_Services_Agreement.pdf" in html
    assert "65/100" in html
    assert "MEDIUM" in html
    assert "Cap liability at fees paid" in html

    # Test Markdown generation
    md = export_service.generate_markdown_report(contract)
    assert "# Contract Review Audit Report: Master_Services_Agreement.pdf" in md
    assert "Risk Score" in md

    # Test JSON generation
    data = export_service.generate_json_report(contract)
    assert data["contract_id"] == 42
    assert data["latest_analysis"]["risk_score"] == 65


def test_clause_rewriter_fallback():
    llm = LLMService()
    # Test heuristic fallback with uncapped indemnification
    sample_clause = "Customer agrees to indemnify and hold harmless the vendor from any and all damages."
    result = llm.rewrite_clause(clause_text=sample_clause, stance="customer_favorable")
    
    assert "original_clause" in result
    assert "rewritten_clause" in result
    assert "key_changes" in result
    assert len(result["key_changes"]) > 0
    assert result["stance"] == "customer_favorable"
