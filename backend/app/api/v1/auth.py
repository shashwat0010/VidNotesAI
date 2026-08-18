from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import jwt, JWTError

from app.core.config import settings
from app.core.db import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.models import User
from app.schemas.schemas import UserCreate, UserResponse, Token

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    email = None
    oauth_id = None
    provider = "email"

    # 1. Try decoding with local SECRET_KEY
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
    except Exception:
        # 2. Try decoding as Supabase JWT
        try:
            if settings.SUPABASE_JWT_SECRET:
                payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
            else:
                # Unverified extraction for seamless token decoding
                payload = jwt.get_unverified_claims(token)
            
            email = payload.get("email") or (payload.get("user_metadata", {}) or {}).get("email")
            oauth_id = str(payload.get("sub", ""))
            provider = (payload.get("app_metadata", {}) or {}).get("provider", "supabase")
        except Exception:
            raise credentials_exception

    if not email:
        raise credentials_exception

    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    
    # Auto-provision Supabase / OAuth user in PostgreSQL if they don't exist yet
    if user is None:
        user = User(
            email=email,
            oauth_provider=provider or "supabase",
            oauth_id=oauth_id,
            is_active=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user

@router.post("/supabase-sync", response_model=Token)
async def supabase_sync(payload: dict, db: AsyncSession = Depends(get_db)):
    """
    Syncs authenticated Supabase user session with backend PostgreSQL database.
    Creates or retrieves the corresponding User record and returns authentication package.
    """
    access_token = payload.get("access_token")
    email = payload.get("email")
    oauth_id = payload.get("id")
    
    if not email and access_token:
        try:
            claims = jwt.get_unverified_claims(access_token)
            email = claims.get("email") or (claims.get("user_metadata", {}) or {}).get("email")
            oauth_id = oauth_id or str(claims.get("sub", ""))
        except Exception:
            pass

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid email required for user synchronization."
        )

    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()

    if not user:
        user = User(
            email=email,
            oauth_provider="supabase",
            oauth_id=str(oauth_id) if oauth_id else None,
            is_active=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif oauth_id and not user.oauth_id:
        user.oauth_id = str(oauth_id)
        user.oauth_provider = "supabase"
        await db.commit()
        await db.refresh(user)

    # Return valid session with token
    token_str = access_token or create_access_token(
        subject=user.email, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {
        "access_token": token_str,
        "token_type": "bearer",
        "user": user
    }

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if email exists
    result = await db.execute(select(User).filter(User.email == user_in.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )
        
    new_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        oauth_provider="email"
    )
    db.add(new_user)
    await db.flush() # Flushes to database to get the user ID
    
    return new_user

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).filter(User.email == form_data.username))
    user = result.scalars().first()
    
    if not user or not user.hashed_password or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

# OAuth mocks for production capability integration
@router.post("/oauth/{provider}")
async def oauth_login(provider: str, token_payload: dict, db: AsyncSession = Depends(get_db)):
    """
    Handles sign-in / sign-up via OAuth (Google / GitHub).
    Extracts email and provider id from client-side checked payload.
    """
    email = token_payload.get("email")
    oauth_id = token_payload.get("id")
    
    if not email or not oauth_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth payload credentials"
        )
        
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    
    if not user:
        # Create user
        user = User(
            email=email,
            oauth_provider=provider,
            oauth_id=str(oauth_id),
            is_active=True
        )
        db.add(user)
        await db.flush()
    else:
        # Link user if they logged in with email before
        if not user.oauth_id:
            user.oauth_id = str(oauth_id)
            user.oauth_provider = provider
            await db.flush()
            
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }
