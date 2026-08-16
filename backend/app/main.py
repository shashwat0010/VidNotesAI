import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.db import init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.folders import router as folders_router
from app.api.v1.videos import router as videos_router
from app.api.v1.chat import router as chat_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing databases and extensions...")
    init_db()
    print("Database initialization complete.")

    if settings.OPENROUTER_API_KEY:
        masked_key = settings.OPENROUTER_API_KEY[:8] + "..." if len(settings.OPENROUTER_API_KEY) > 8 else "***"
        print(f"[LLM Status] OpenRouter configured cleanly: {masked_key} (Model: {settings.OPENROUTER_MODEL})")
    elif settings.OPENAI_API_KEY:
        print("[LLM Status] OpenAI API configured.")
    elif settings.GEMINI_API_KEY:
        print("[LLM Status] Gemini API configured.")
    elif settings.MISTRAL_API_KEY:
        print("[LLM Status] Mistral API configured.")
    else:
        print("[LLM Status] Notice: No active LLM API key detected. Using default offline fallback.")
    yield
    # Shutdown tasks
    print("Shutting down API server...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:80",
        "http://127.0.0.1:80"
    ],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler for unhandled errors with CORS preservation
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled error in path {request.url.path}: {exc}")
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    )

# Mount Local Static Image Storage (/uploads and /vidnotes-storage)
uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
app.mount("/vidnotes-storage", StaticFiles(directory=uploads_dir), name="vidnotes-storage")

# Mount APIRouters
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(folders_router, prefix=f"{settings.API_V1_STR}/folders", tags=["folders"])
app.include_router(videos_router, prefix=f"{settings.API_V1_STR}/videos", tags=["videos"])
app.include_router(chat_router, prefix=f"{settings.API_V1_STR}/chat", tags=["chat"])

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "api_v1_docs": "/docs"
    }
