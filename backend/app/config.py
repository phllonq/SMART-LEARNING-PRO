import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # APP
    PROJECT_NAME: str = "SMART LEARNING PRO"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    # SECURITY & JWT
    SECRET_KEY: str = "smart-learning-pro-super-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # DATABASE
    # Fallback to local SQLite database in database/smart_learning.db
    DATABASE_URL: str = "sqlite+aiosqlite:///./database/smart_learning.db"
    DATABASE_URL_SYNC: str = "sqlite:///./database/smart_learning.db"

    # REDIS / CACHE
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_IN_MEMORY_CACHE_FALLBACK: bool = True

    # AI CONFIGURATION
    AI_PROVIDER: str = Field(default="mock", validation_alias="AI_PROVIDER")  # "mock" or "google"
    GEMINI_API_KEY: str = Field(default="", validation_alias="GEMINI_API_KEY")
    GEMINI_MODEL: str = Field(default="gemini-3.8-flash", validation_alias="GEMINI_MODEL")
    AI_TIMEOUT_SECONDS: float = Field(default=15.0, validation_alias="AI_TIMEOUT_SECONDS")
    AI_MAX_RETRIES: int = Field(default=2, validation_alias="AI_MAX_RETRIES")
    AI_RETRY_BACKOFF_BASE: float = Field(default=0.5, validation_alias="AI_RETRY_BACKOFF_BASE")

    # STORAGE
    STORAGE_TYPE: str = "local"
    LOCAL_STORAGE_PATH: str = "./storage"

    # ADMIN BOOTSTRAP
    INITIAL_ADMIN_EMAIL: str = "admin@smartlearning.vn"
    INITIAL_ADMIN_PASSWORD: str = "AdminSecurePassword123!"
    INITIAL_ADMIN_NAME: str = "System Administrator"


settings = Settings()
