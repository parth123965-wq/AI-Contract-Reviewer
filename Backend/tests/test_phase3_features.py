from ai_engine.services.llm_service import LLMService
from app.schemas.playbook import PlaybookCreate, PlaybookRule


def test_contract_comparison_fallback():
    llm = LLMService()
    base_text = "Section 1: Payment shall be due within 30 days of invoice.\n\nSection 2: Total liability shall be capped at 100,000 USD."
    target_text = "Section 1: Payment shall be due within 60 days of invoice.\n\nSection 2: Vendor liability is unlimited and uncapped."

    result = llm.compare_contracts(base_text=base_text, target_text=target_text)

    assert "similarity_score" in result
    assert isinstance(result["similarity_score"], float)
    assert "summary_of_changes" in result
    assert "differences" in result
    assert isinstance(result["differences"], list)


def test_playbook_schema_validation():
    rule = PlaybookRule(
        title="Liability Cap",
        condition="Must be capped at 1x annual fee",
        severity="HIGH"
    )
    playbook_data = PlaybookCreate(
        name="Enterprise Standard",
        description="Standard procurement policy",
        rules=[rule],
        is_default=True
    )
    assert playbook_data.name == "Enterprise Standard"
    assert len(playbook_data.rules) == 1
    assert playbook_data.rules[0].severity == "HIGH"
