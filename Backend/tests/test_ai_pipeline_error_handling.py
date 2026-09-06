import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from unittest.mock import MagicMock, patch

from ai_engine.graph.nodes import ContractNodes
from ai_engine.graph.graph import ContractGraph
from app.models.contract import ContractStatus


@pytest.fixture
def base_state():
    return {
        "contract_id": 1,
        "user_id": 1,
        "file_path": "non_existent_file.pdf",
        "analysis_version": 1,
        "status": ContractStatus.PROCESSING,
        "error": None,
        "extracted_text": "",
        "chunks": [],
        "embeddings": [],
        "query_embedding": [],
        "retrieved_chunks": [],
        "summary": "",
        "risk_score": 0,
        "suggestions": [],
        "prompt": "",
        "llm_response": "",
        "analysis_result": None,
        "processing_time_ms": 0,
        "db": None
    }


def test_extract_text_node_nonexistent_file(base_state):
    nodes = ContractNodes()
    res_state = nodes.extract_text_node(base_state)
    assert res_state["status"] == ContractStatus.FAILED
    assert res_state["error"] is not None
    assert "File is not found" in res_state["error"]


def test_nodes_short_circuit_on_error(base_state):
    nodes = ContractNodes()
    base_state["status"] = ContractStatus.FAILED
    base_state["error"] = "Previous node failed"

    # All nodes should short-circuit and return state unchanged without raising exceptions
    res_chunk = nodes.chunk_text_node(base_state)
    assert res_chunk["error"] == "Previous node failed"

    res_emb = nodes.embedding_node(base_state)
    assert res_emb["error"] == "Previous node failed"

    res_store = nodes.store_vector_node(base_state)
    assert res_store["error"] == "Previous node failed"

    res_llm = nodes.llm_node(base_state)
    assert res_llm["error"] == "Previous node failed"


def test_llm_node_exception_handling(base_state):
    nodes = ContractNodes()
    base_state["prompt"] = "Analyze contract"
    
    with patch.object(nodes.llm_service, "generate", side_effect=RuntimeError("LLM Provider Timeout")):
        res_state = nodes.llm_node(base_state)
        assert res_state["status"] == ContractStatus.FAILED
        assert "LLM Provider Timeout" in res_state["error"]


def test_embedding_node_exception_handling(base_state):
    nodes = ContractNodes()
    base_state["chunks"] = ["Sample clause 1", "Sample clause 2"]

    with patch.object(nodes.embedding_service, "create_embeddings", side_effect=ValueError("Embedding error")):
        res_state = nodes.embedding_node(base_state)
        assert res_state["status"] == ContractStatus.FAILED
        assert "Embedding error" in res_state["error"]


def test_full_graph_execution_with_invalid_file(base_state):
    contract_graph = ContractGraph().compile_graph()
    final_state = contract_graph.invoke(base_state)
    
    assert final_state["status"] == ContractStatus.FAILED
    assert final_state["error"] is not None
