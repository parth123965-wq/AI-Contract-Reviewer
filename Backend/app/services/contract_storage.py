import asyncio
import os
import tempfile
from pathlib import Path

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

    async def download_to_tempfile(self, object_path: str) -> Path:
        legacy_local_path = Path(object_path)
        if legacy_local_path.is_file():
            content = await asyncio.to_thread(legacy_local_path.read_bytes)
        else:
            content = await asyncio.to_thread(
                self.client.storage.from_(self.BUCKET_NAME).download,
                object_path,
            )
        file_descriptor, temporary_path = tempfile.mkstemp(suffix=".pdf")
        try:
            with os.fdopen(file_descriptor, "wb") as temporary_file:
                temporary_file.write(content)
        except Exception:
            Path(temporary_path).unlink(missing_ok=True)
            raise
        return Path(temporary_path)

    async def remove(self, object_path: str) -> None:
        await asyncio.to_thread(
            self.client.storage.from_(self.BUCKET_NAME).remove,
            [object_path],
        )
