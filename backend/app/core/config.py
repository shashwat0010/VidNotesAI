import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "VidNotes AI"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "supersecretkey_change_me_in_production_1234567890"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # CORS Origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://localhost:80",
        "http://127.0.0.1"
    ]
    
    # Database Configuration
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "vidnotes"
    POSTGRES_PORT: str = "5432"
    
    @property
    def DATABASE_URL_ASYNC(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
    @property
    def DATABASE_URL_SYNC(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis (Celery + Cache)
    REDIS_URL: str = "redis://localhost:6379/0"

    # AWS S3 / MinIO Configuration
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "vidnotes-storage"
    S3_ENDPOINT_URL: Optional[str] = "http://localhost:9000"  # For local MinIO, set to None for AWS S3
    
    # AI Providers Configuration
    # We allow running both OpenAI or Gemini. If key is provided, we use the active one.
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_VISION_MODEL: str = "gpt-4o"
    
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_MODEL: str = "mistral-large-latest"
    MISTRAL_VISION_MODEL: str = "pixtral-12b-2409"

    
    # Faster Whisper settings
    # Options: tiny, base, small, medium, large-v3
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"  # cpu or cuda
    WHISPER_COMPUTE_TYPE: str = "int8"  # int8, float16 etc

    # Video Upload settings
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB
    UPLOAD_DIR: str = "/tmp/vidnotes_uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Clean up placeholder API keys if left unchanged by the user
def clean_placeholder_keys(s: Settings):
    for attr in ["OPENAI_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY"]:
        val = getattr(s, attr)
        if val and (val.startswith("your_") or "placeholder" in val.lower()):
            setattr(s, attr, None)

clean_placeholder_keys(settings)

# Ensure temp upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

