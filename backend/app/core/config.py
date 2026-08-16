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
    
    # Database Configuration (Cloud PostgreSQL / Supabase / Neon / RDS)
    DATABASE_URL: Optional[str] = None
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "vidnotes"
    POSTGRES_PORT: str = "5432"
    USE_SQLITE: bool = True
    
    @property
    def DATABASE_URL_ASYNC(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            # asyncpg uses ssl=require instead of sslmode=require
            if "sslmode=" in url:
                url = url.replace("sslmode=require", "ssl=require").replace("sslmode=prefer", "ssl=prefer").replace("sslmode=disable", "ssl=disable")
            elif "ssl=" not in url and "oregon-postgres" in url:
                url = url + ("&ssl=require" if "?" in url else "?ssl=require")
            return url
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
    @property
    def DATABASE_URL_SYNC(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            # psycopg uses sslmode=require
            if "ssl=" in url and "sslmode=" not in url:
                url = url.replace("ssl=require", "sslmode=require")
            elif "sslmode=" not in url and "oregon-postgres" in url:
                url = url + ("&sslmode=require" if "?" in url else "?sslmode=require")
            return url
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Celery Broker (RabbitMQ) & Redis (Cache / Transient state)
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"
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

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    OPENROUTER_VISION_MODEL: str = "nvidia/nemotron-nano-12b-v2-vl:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Faster Whisper settings
    # Options: tiny, base, small, medium, large-v3
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"  # cpu or cuda
    WHISPER_COMPUTE_TYPE: str = "int8"  # int8, float16 etc

    # Video Upload settings
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB
    UPLOAD_DIR: str = "/tmp/vidnotes_uploads"

    model_config = SettingsConfigDict(
        env_file=[
            r"C:\Users\tshas\vid_notes\VidNotesAI\.env",
            r"C:\Users\tshas\vid_notes\VidNotesAI\backend\.env",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
            ".env"
        ],
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

def clean_placeholder_keys(s: Settings):
    placeholders = {
        "your_openrouter_api_key_here",
        "your_openai_api_key_here",
        "your_gemini_api_key_here",
        "your_mistral_api_key_here",
    }
    for attr in ["OPENAI_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY"]:
        val = getattr(s, attr)
        if val:
            v_str = str(val).strip()
            if v_str in placeholders or (v_str.startswith("your_") and len(v_str) < 30):
                if attr == "OPENROUTER_API_KEY":
                    print("[LLM Notice] OPENROUTER_API_KEY is set to placeholder text ('your_openrouter_api_key_here').")
                    print("[LLM Notice] Please replace 'your_openrouter_api_key_here' in .env with your actual key starting with 'sk-or-v1-'.")
                setattr(s, attr, None)

clean_placeholder_keys(settings)

# Ensure temp upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

