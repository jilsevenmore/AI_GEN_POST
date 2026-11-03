from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.common import (
    UserRegister, UserLogin, UserResponse, Token, TokenPayload,
    BrandKitCreate, BrandKitUpdate, BrandKitResponse
)
from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from jose import jwt
from datetime import timedelta
from uuid import UUID

router = APIRouter()
settings = get_settings()


# Mock user store (replace with real DB in Phase 2)
MOCK_USERS = {}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user and company."""
    # TODO: Implement real registration with DB
    # For now, return mock response
    from uuid import uuid4
    from datetime import datetime
    return UserResponse(
        id=uuid4(),
        email=user_data.email,
        company_id=uuid4(),
        is_active=True,
        created_at=datetime.utcnow(),
    )


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """Login with email/password, return JWT tokens."""
    # TODO: Implement real authentication
    # Mock: accept any credentials
    from uuid import uuid4
    user_id = uuid4()
    company_id = uuid4()
    access_token = create_access_token(subject=user_id, company_id=company_id)
    refresh_token = create_refresh_token(subject=user_id, company_id=company_id)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token."""
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = UUID(payload["sub"])
        company_id = UUID(payload["company_id"])
        new_access = create_access_token(subject=user_id, company_id=company_id)
        new_refresh = create_refresh_token(subject=user_id, company_id=company_id)
        return Token(access_token=new_access, refresh_token=new_refresh)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me", response_model=UserResponse)
async def get_current_user(db: AsyncSession = Depends(get_db)):
    """Get current user info (requires auth)."""
    # TODO: Implement with real auth dependency
    from uuid import uuid4
    from datetime import datetime
    return UserResponse(
        id=uuid4(),
        email="demo@example.com",
        company_id=uuid4(),
        is_active=True,
        created_at=datetime.utcnow(),
    )


@router.post("/logout")
async def logout():
    """Logout (client-side token removal)."""
    return {"message": "Logged out successfully"}