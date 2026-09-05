from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    UPLOAD_DIR: str
    LOG_LEVEL: str
    MODEL_NAME: str
    COLLECTION_NAME: str
    CHROMA_DB_PATH: str
    AI_MODEL_NAME: str
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    REDIS_URL: str
    MAIL_USERNAME: str | None = None
    MAIL_PASSWORD: str | None = None
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str | None = None
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    OTP_LENGTH: int
    OTP_EXPIRE_SECONDS: int
    OTP_COOLDOWN_SECONDS: int
    OTP_MAX_ATTEMPTS: int
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        extra='ignore'
    )
    
settings = Settings()