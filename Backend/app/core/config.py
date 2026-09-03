from pydantic_settings import BaseSettings , SettingsConfigDict

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
    model_config = SettingsConfigDict(
        env_file='.env',
        extra='ignore'
    )
    
settings = Settings()