import asyncio

from supabase import Client, create_client

from app.core.config import settings


class ContractStorage:
    BUCKET_NAME = "uploads"

    def __init__(self, client: Client | None = None):
        self.client = client or create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SECRET_KEY,
        )

    async def upload(self, object_path: str, content: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.storage.from_(self.BUCKET_NAME).upload,
            object_path,
            content,
            {"content-type": content_type, "upsert": "false"},
        )

    async def download(self, object_path: str) -> bytes:
        return await asyncio.to_thread(
            self.client.storage.from_(self.BUCKET_NAME).download,
            object_path,
        )

    async def remove(self, object_path: str) -> None:
        await asyncio.to_thread(
            self.client.storage.from_(self.BUCKET_NAME).remove,
            [object_path],
        )
