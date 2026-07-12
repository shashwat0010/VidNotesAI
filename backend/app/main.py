from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.db import init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.folders import router as folders_router
from app.api.v1.videos import router as videos_router
from app.api.v1.chat import router as chat_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks: initialize tables and pgvector extension
    print("Initializing databases and extensions...")
    init_db()
    print("Database initialization complete.")
    yield
    # Shutdown tasks
    print("Shutting down API server...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set CORS origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled error in path {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Check backend console logs."}
    )

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
