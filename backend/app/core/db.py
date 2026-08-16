from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from app.core.config import settings

is_sqlite = settings.USE_SQLITE and not settings.DATABASE_URL

if is_sqlite:
    async_engine = create_async_engine("sqlite+aiosqlite:///./vidnotes.db", echo=False)
    sync_engine = create_engine("sqlite:///./vidnotes.db", echo=False)
else:
    async_engine = create_async_engine(
        settings.DATABASE_URL_ASYNC,
        echo=False,
        future=True,
        pool_pre_ping=True
    )
    sync_engine = create_engine(
        settings.DATABASE_URL_SYNC,
        echo=False,
        pool_pre_ping=True
    )

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

# Dependency to get db session in FastAPI routes
async def get_db():
    session_factory = AsyncSessionLocal
    try:
        session = session_factory()
    except Exception as e:
        print(f"Failed to create session with primary engine: {e}. Re-initializing fallback...")
        init_db()
        session_factory = AsyncSessionLocal
        session = session_factory()

    async with session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def check_postgres_available() -> bool:
    try:
        test_engine = create_engine(settings.DATABASE_URL_SYNC, connect_args={"connect_timeout": 1})
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        test_engine.dispose()
        return True
    except Exception as e:
        print(f"PostgreSQL pre-flight check notice ({e}). Defaulting to SQLite database (vidnotes.db)...")
        return False

def init_db():
    global async_engine, sync_engine, AsyncSessionLocal, SessionLocal
    is_postgres = False
    
    if not settings.USE_SQLITE:
        try:
            with sync_engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
            is_postgres = True
        except Exception as e:
            print(f"PostgreSQL initialization notice: {e}. Falling back to SQLite...")
            is_postgres = False

    if not is_postgres:
        print("Using local SQLite database (vidnotes.db)...")
        sqlite_sync_url = "sqlite:///./vidnotes.db"
        sqlite_async_url = "sqlite+aiosqlite:///./vidnotes.db"
        sync_engine = create_engine(sqlite_sync_url, echo=False)
        async_engine = create_async_engine(sqlite_async_url, echo=False)
        AsyncSessionLocal = async_sessionmaker(
            bind=async_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        SessionLocal = sessionmaker(
            bind=sync_engine,
            autocommit=False,
            autoflush=False
        )

    try:
        from app.models.models import User, Folder, Video, TranscriptSegment, Keyframe, NoteOutput, ChunkEmbedding, ChatMessage
        Base.metadata.create_all(bind=sync_engine)
        print("Database tables initialized successfully.")
    except Exception as e:
        print(f"Database table creation notice: {e}")
