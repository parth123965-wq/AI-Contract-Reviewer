from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.models.contract import Contract, ContractStatus
from app.models.user import User
from app.services.contract_service import ContractService
from app.services.contract_storage import ContractStorage


def make_upload(filename="agreement.pdf", content=b"%PDF-1.7 test", content_type="application/pdf"):
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


def make_contract(file_path):
    return Contract(
        id=1,
        user_id=2,
        original_filename="agreement.pdf",
        stored_filename="stored.pdf",
        file_path=str(file_path),
        file_size=13,
        content_type="application/pdf",
        status=ContractStatus.UPLOADED,
        created_at=datetime.now(timezone.utc),
        analyses=[],
    )


@pytest.fixture
def service():
    instance = ContractService()
    instance.contract_repository = AsyncMock()
    instance.contract_storage = AsyncMock()
    return instance


@pytest.mark.asyncio
async def test_upload_saves_valid_pdf_to_supabase_and_returns_contract(service):
    user = User(id=2, username="tester", email="test@example.com", password_hash="hash")
    file = make_upload()
    service.contract_repository.create_contract.side_effect = (
        lambda db, contract: make_contract(contract.file_path)
    )

    result = await service.upload_contract(AsyncMock(), user, file)

    assert result.original_filename == "agreement.pdf"
    assert result.status == ContractStatus.UPLOADED
    saved_contract = service.contract_repository.create_contract.await_args.kwargs["contract"]
    assert saved_contract.user_id == user.id
    assert saved_contract.file_path == f"{user.id}/{saved_contract.stored_filename}"
    service.contract_storage.upload.assert_awaited_once_with(
        object_path=saved_contract.file_path,
        content=b"%PDF-1.7 test",
        content_type="application/pdf",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content", "content_type", "detail"),
    [
        ("agreement.txt", b"%PDF-1.7", "application/pdf", "Only PDF files"),
        ("agreement.pdf", b"%PDF-1.7", "text/plain", "content type"),
        ("agreement.pdf", b"not a pdf", "application/pdf", "Invalid PDF"),
        ("agreement.pdf", b"", "application/pdf", "cannot be empty"),
    ],
)
async def test_upload_rejects_invalid_files(
    service, filename, content, content_type, detail
):
    db = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.upload_contract(
            db,
            User(id=2, username="tester", email="test@example.com", password_hash="hash"),
            make_upload(filename, content, content_type),
        )

    assert error.value.status_code == 400
    assert detail.lower() in error.value.detail.lower()
    db.rollback.assert_awaited_once()
    service.contract_storage.upload.assert_not_awaited()
    service.contract_repository.create_contract.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rejects_files_over_size_limit(service):
    content = b"%PDF" + (b"x" * ContractService.MAX_FILE_SIZE)
    db = AsyncMock()

    with pytest.raises(HTTPException, match="maximum allowed limit"):
        await service.upload_contract(
            db,
            User(id=2, username="tester", email="test@example.com", password_hash="hash"),
            make_upload(content=content),
        )

    db.rollback.assert_awaited_once()
    service.contract_storage.upload.assert_not_awaited()
    service.contract_repository.create_contract.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rolls_back_and_removes_supabase_object_if_repository_fails(service):
    service.contract_repository.create_contract.side_effect = RuntimeError("database failed")
    db = AsyncMock()

    with pytest.raises(RuntimeError, match="database failed"):
        await service.upload_contract(
            db,
            User(id=2, username="tester", email="test@example.com", password_hash="hash"),
            make_upload(),
        )

    db.rollback.assert_awaited_once()
    service.contract_storage.remove.assert_awaited_once()


@pytest.mark.asyncio
async def test_contract_storage_downloads_private_object_to_temporary_file():
    bucket = Mock()
    bucket.download.return_value = b"%PDF-1.7 test"
    client = Mock()
    client.storage.from_.return_value = bucket
    storage = ContractStorage(client)

    temporary_file = await storage.download_to_tempfile("2/contract.pdf")

    try:
        assert temporary_file.read_bytes() == b"%PDF-1.7 test"
        client.storage.from_.assert_called_once_with("uploads")
        bucket.download.assert_called_once_with("2/contract.pdf")
    finally:
        temporary_file.unlink()


@pytest.mark.asyncio
async def test_contract_storage_reads_legacy_local_file_without_removing_it(tmp_path):
    legacy_file = tmp_path / "legacy-contract.pdf"
    legacy_file.write_bytes(b"%PDF-1.7 legacy")
    client = Mock()
    storage = ContractStorage(client)

    temporary_file = await storage.download_to_tempfile(str(legacy_file))

    try:
        assert temporary_file.read_bytes() == b"%PDF-1.7 legacy"
        assert legacy_file.read_bytes() == b"%PDF-1.7 legacy"
        client.storage.from_.assert_not_called()
    finally:
        temporary_file.unlink()


@pytest.mark.asyncio
async def test_contract_lookup_is_scoped_to_authenticated_user(service):
    db = AsyncMock()
    user = User(id=17, username="tester", email="test@example.com", password_hash="hash")
    contract = make_contract("contract.pdf")
    service.contract_repository.get_contract_by_id.return_value = contract

    result = await service.get_contract_by_id(db, 4, user)

    assert result is contract
    service.contract_repository.get_contract_by_id.assert_awaited_once_with(
        db=db,
        contract_id=4,
        user_id=user.id,
    )


@pytest.mark.asyncio
async def test_contract_lookup_returns_404_when_not_found(service):
    service.contract_repository.get_contract_by_id.return_value = None

    with pytest.raises(HTTPException) as error:
        await service.get_contract_by_id(AsyncMock(), 4, User(id=17))

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_contract_soft_deletes_owned_contract(service):
    user = User(id=17)
    contract = make_contract("contract.pdf")
    service.contract_repository.get_contract_by_id.return_value = contract

    await service.delete_contract(AsyncMock(), contract.id, user)

    service.contract_repository.soft_delete_contract.assert_awaited_once_with(
        db=service.contract_repository.get_contract_by_id.await_args.kwargs["db"],
        contract=contract,
    )
