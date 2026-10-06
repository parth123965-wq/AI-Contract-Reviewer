from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool
    PRODUCTION: bool = False
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    UPLOAD_DIR: str
    LOG_LEVEL: str
    EMBEDDING_MODEL: str
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str
    PINECONE_CLOUD: str 
    PINECONE_REGION: str
    AI_MODEL_NAME: str
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    REDIS_URL: str
    GMAIL_CLIENT_ID: str | None = None
    GMAIL_CLIENT_SECRET: str | None = None
    GMAIL_REFRESH_TOKEN: str | None = None
    GMAIL_SENDER: str | None = None
    OTP_LENGTH: int
    OTP_EXPIRE_SECONDS: int
    OTP_COOLDOWN_SECONDS: int
    OTP_MAX_ATTEMPTS: int
    ALLOWED_ORIGINS: str = "*"
    SUPABASE_SECRET_KEY: str
    SUPABASE_URL: str
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        extra='ignore'
    )
    
settings = Settings()