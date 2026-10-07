from types import SimpleNamespace

import pytest

from ai_engine.services import vector_store_service as vector_module
from ai_engine.services.vector_store_service import VectorStoreService


class FakeIndex:
    def __init__(self):
        self.upserted_vectors = None
        self.query_args = None
        self.query_result = SimpleNamespace(
            matches=[
                SimpleNamespace(metadata={"text": "Relevant contract clause."}),
                SimpleNamespace(metadata={"text": "12"}),
                SimpleNamespace(metadata={"text": "  "}),
            ]
        )

    def upsert(self, *, vectors):
        self.upserted_vectors = vectors

    def query(self, **kwargs):
        self.query_args = kwargs
        return self.query_result


class FakePineconeClient:
    def __init__(self, *, api_key):
        assert api_key == "test-pinecone-key"
        self.names = set()
        self.created_index = None
        self.index = FakeIndex()

    def list_indexes(self):
        return SimpleNamespace(names=lambda: list(self.names))

    def create_index(self, **kwargs):
        self.created_index = kwargs
        self.names.add(kwargs["name"])

    def describe_index(self, name):
        assert name == "contracts"
        return SimpleNamespace(
            status={"ready": True},
            dimension=self.created_index["dimension"],
        )

    def Index(self, name):
        assert name == "contracts"
        return self.index


@pytest.fixture
def fake_client(monkeypatch):
    client = FakePineconeClient(api_key="test-pinecone-key")
    monkeypatch.setattr(
        vector_module,
        "Pinecone",
        lambda **kwargs: client,
    )
    return client


def test_store_embeddings_creates_index_using_actual_embedding_dimension(fake_client):
    service = VectorStoreService()

    service.store_embeddings(
        contract_id=7,
        user_id=12,
        chunks=["First clause.", "Second clause."],
        embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        version=2,
    )

    assert fake_client.created_index["name"] == "contracts"
    assert fake_client.created_index["dimension"] == 3
    assert fake_client.created_index["metric"] == "cosine"
    assert fake_client.created_index["spec"].cloud == "aws"
    assert fake_client.created_index["spec"].region == "ap-southeast-1"
    assert [vector["id"] for vector in fake_client.index.upserted_vectors] == [
        "contract_7_v2_chunk_0",
        "contract_7_v2_chunk_1",
    ]
    assert fake_client.index.upserted_vectors[0]["metadata"] == {
        "contract_id": 7,
        "user_id": 12,
        "chunk_index": 0,
        "analysis_version": 2,
        "text": "First clause.",
    }


def test_search_filters_to_contract_and_owner(fake_client):
    service = VectorStoreService()
    service._get_index(dimension=3)

    results = service.search(
        contract_id=7,
        user_id=12,
        query_embedding=[0.1, 0.2, 0.3],
        top_k=5,
    )

    assert results == ["Relevant contract clause."]
    assert fake_client.index.query_args == {
        "vector": [0.1, 0.2, 0.3],
        "top_k": 5,
        "filter": {
            "contract_id": {"$eq": 7},
            "user_id": {"$eq": 12},
        },
        "include_metadata": True,
    }


def test_store_rejects_mismatched_embedding_dimensions(fake_client):
    service = VectorStoreService()

    with pytest.raises(ValueError, match="same dimension"):
        service.store_embeddings(
            contract_id=7,
            user_id=12,
            chunks=["First clause.", "Second clause."],
            embeddings=[[0.1, 0.2], [0.3]],
            version=1,
        )

    assert fake_client.created_index is None


def test_empty_query_returns_without_accessing_index(fake_client):
    service = VectorStoreService()

    assert service.search(
        contract_id=7,
        user_id=12,
        query_embedding=[],
    ) == []
    assert fake_client.created_index is None
