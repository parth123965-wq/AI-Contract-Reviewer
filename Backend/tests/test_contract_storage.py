from types import SimpleNamespace

import pytest

from app.services.contract_storage import ContractStorage


class StorageBucket:
    def __init__(self):
        self.removed_paths = None

    def remove(self, paths):
        self.removed_paths = paths


class StorageClient:
    def __init__(self):
        self.bucket = StorageBucket()
        self.storage = SimpleNamespace(from_=lambda bucket_name: self.bucket)


@pytest.mark.asyncio
async def test_remove_many_deletes_all_requested_objects():
    client = StorageClient()

    await ContractStorage(client=client).remove_many(
        ["7/active.pdf", "7/soft-deleted.pdf"]
    )

    assert client.bucket.removed_paths == ["7/active.pdf", "7/soft-deleted.pdf"]


@pytest.mark.asyncio
async def test_remove_many_does_not_call_storage_for_empty_list():
    client = StorageClient()

    await ContractStorage(client=client).remove_many([])

    assert client.bucket.removed_paths is None
