from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException , UploadFile , status
from sqlalchemy.orm import Session
from app.models.contract import Contract , ContractStatus
from app.models.user import User
from app.repositories.contract_repository import ContractRepository
from app.schemas.contract import ContractResponse , ContractListResponse
from app.core.config import settings
import shutil
from typing import Optional

class ContractService:
    MAX_FILE_SIZE = 20 * 1024 * 1024
    
    def __init__(self):
        self.contract_repository = ContractRepository()
        
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
        file.file.seek(0,2)
        size = file.file.tell()
        file.file.seek(0)
        if size > self.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds the maximum allowed limit."
            )
        return size
    
    def _generate_filename(
        self,
        file: UploadFile
    ) -> str:
        suffix = Path(file.filename).suffix.lower()
        filename = f"{uuid4()}{suffix}"
        return filename
    
    def _save_file(
        self,
        file: UploadFile,
        stored_filename: str
    ) -> str:
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        file_path = upload_dir / stored_filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(
                file.file,
                buffer
            )
        return str(file_path)
    
    def upload_contract(
        self,
        db: Session,
        current_user: User,
        file: UploadFile
    ) -> ContractResponse:
        file_path = None
        try:
            self._validate_extension(file=file)
            self._validate_content_type(file=file)
            file_size = self._validate_file_size(file=file)
            stored_filename = self._generate_filename(file=file)
            file_path = self._save_file(
                file=file,
                stored_filename=stored_filename
            )
            contract = Contract(
                user_id = current_user.id,
                original_filename = file.filename,
                stored_filename = stored_filename,
                file_path = file_path,
                file_size = file_size,
                content_type = file.content_type,
                status = ContractStatus.UPLOADED
            )
            saved_contract = self.contract_repository.create_contract(
                db=db,
                contract=contract
            )
            return ContractResponse.model_validate(
                saved_contract
            )
        except Exception:
            db.rollback()
            if file_path is not None and Path(file_path).exists():
                Path(file_path).unlink()
            raise
    
    def get_user_contracts(
        self,
        db: Session,
        current_user: User
    ) -> ContractListResponse:
        return self.contract_repository.get_user_contracts(
            db=db,
            user_id=current_user.id
        )
        
    def get_contract_by_id(
        self,
        db: Session,
        contract_id: int,
        current_user: User
    ) -> Contract:
        contract = self.contract_repository.get_contract_by_id(
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
        
    def delete_contract(
        self,
        db: Session,
        contract_id: int,
        current_user: User
    ) -> Contract:
        contract = self.get_contract_by_id(
            db=db,
            contract_id=contract_id,
            current_user=current_user
        )
        return self.contract_repository.soft_delete_contract(
            db=db,
            contract=contract
        )
                            
def contract_service() -> ContractService:
    return ContractService()