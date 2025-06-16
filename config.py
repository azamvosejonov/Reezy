from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./test.db"
    SQLALCHEMY_DB_TABLE_PREFIX: str = ""
    
    # JWT Authentication
    SECRET_KEY: str = "supersecretkey"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Media
    MEDIA_ROOT: str = "media"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]
    
    model_config = SettingsConfigDict(env_file=".env", extra='ignore')

settings = Settings()
