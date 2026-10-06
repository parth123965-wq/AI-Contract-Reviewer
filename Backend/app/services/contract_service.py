from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException , UploadFile , status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.contract import Contract , ContractStatus
from app.models.user import User
from app.repositories.contract_repository import ContractRepository
from app.schemas.contract import ContractResponse , ContractListResponse
from app.services.contract_storage import ContractStorage
from app.core.logger import get_app_logger

logger = get_app_logger("services.contract")

class ContractService:
    MAX_FILE_SIZE = 20 * 1024 * 1024
    
    def __init__(self):
        self.contract_repository = ContractRepository()
        self.contract_storage = ContractStorage()
        
    def _validate_extension(
        self,
        file: UploadFile
    ) -> None:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name is not Found"
            )
        suffix = Path(file.filename).suffix.lower()
        if suffix != ".pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed."
            )
        
    def _validate_content_type(
        self,
        file: UploadFile
    ) -> None:
        if file.content_type != "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only application/pdf content type is allowed."
            )
        
    def _validate_file_size(
        self,
        file: UploadFile
    ) -> int:
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        if size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file cannot be empty."
            )
        if size > self.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds the maximum allowed limit."
            )
        return size
    
    def _validate_magic_bytes(
        self,
        file: UploadFile
    ) -> None:
        header = file.file.read(4)
        file.file.seek(0)
        if header != b"%PDF":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file format."
            )

    def _generate_filename(
        self,
        file: UploadFile
    ) -> str:
        suffix = Path(file.filename).suffix.lower()
        filename = f"{uuid4()}{suffix}"
        return filename
    
    async def upload_contract(
        self,
        db: AsyncSession,
        current_user: User,
        file: UploadFile
    ) -> ContractResponse:
        file_path = None
        uploaded_to_storage = False
        try:
            self._validate_extension(file=file)
            self._validate_content_type(file=file)
            file_size = self._validate_file_size(file=file)
            self._validate_magic_bytes(file=file)
            stored_filename = self._generate_filename(file=file)
            file_path = f"{current_user.id}/{stored_filename}"
            await self.contract_storage.upload(
                object_path=file_path,
                content=file.file.read(),
                content_type=file.content_type,
            )
            uploaded_to_storage = True
            contract = Contract(
                user_id = current_user.id,
                original_filename = file.filename,
                stored_filename = stored_filename,
                file_path = file_path,
                file_size = file_size,
                content_type = file.content_type,
                status = ContractStatus.UPLOADED
            )
            saved_contract = await self.contract_repository.create_contract(
                db=db,
                contract=contract
            )
            return ContractResponse.model_validate(
                saved_contract
            )
        except Exception:
            await db.rollback()
            if file_path is not None and uploaded_to_storage:
                try:
                    await self.contract_storage.remove(file_path)
                except Exception:
                    logger.exception(
                        "Failed to remove uploaded contract after upload transaction failed",
                        extra={"object_path": file_path},
                    )
            raise
    
    async def get_user_contracts(
        self,
        db: AsyncSession,
        current_user: User
    ) -> ContractListResponse:
        return await self.contract_repository.get_user_contracts(
            db=db,
            user_id=current_user.id
        )
        
    async def get_contract_by_id(
        self,
        db: AsyncSession,
        contract_id: int,
        current_user: User
    ) -> Contract:
        contract = await self.contract_repository.get_contract_by_id(
            db=db,
            contract_id=contract_id,
            user_id=current_user.id
        )
        if contract == None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract Not Found."
            )
        elif contract.is_deleted == True:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract Not Found."
            )
        else:
            return contract
        
    async def delete_contract(
        self,
        db: AsyncSession,
        contract_id: int,
        current_user: User
    ) -> Contract:
        contract = await self.get_contract_by_id(
            db=db,
            contract_id=contract_id,
            current_user=current_user
        )
        return await self.contract_repository.soft_delete_contract(
            db=db,
            contract=contract
        )
                            
def contract_service() -> ContractService:
    return ContractService()