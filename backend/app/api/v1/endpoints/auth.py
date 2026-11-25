from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from app.db.session import get_db
from app.schemas.common import (
    UserRegister, UserResponse, Token, UserLogin,
    ForgotPasswordRequest, ForgotPasswordResponse,
    ResetPasswordRequest, ResetPasswordResponse,
)
from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash, decode_token
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.company import Company
from app.models.brand_kit import BrandKit
from app.models.quota import Quota
from app.services.email import send_reset_code

router = APIRouter()
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user and company."""
    # Check if email already exists
    existing_user = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create company
    company = Company(name=user_data.company_name)
    db.add(company)
    await db.flush()  # Get company ID
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        company_id=company.id,
    )
    db.add(user)
    
    # Create default brand kit
    brand_kit = BrandKit(
        company_id=company.id,
        company_name=user_data.company_name,
    )
    db.add(brand_kit)
    
    # Create default quota
    quota = Quota(company_id=company.id)
    db.add(quota)
    
    try:
        await db.commit()
        await db.refresh(user)
        await db.refresh(company)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed",
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        company_id=user.company_id,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Login with email/password, return JWT tokens."""
    # Find user by email
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    access_token = create_access_token(subject=user.id, company_id=user.company_id)
    refresh_token = create_refresh_token(subject=user.id, company_id=user.company_id)
    
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = UUID(payload["sub"])
        company_id = UUID(payload["company_id"])
        
        # Verify user still exists and is active
        result = await db.execute(
            select(User).where(User.id == user_id, User.company_id == company_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        new_access = create_access_token(subject=user.id, company_id=user.company_id)
        new_refresh = create_refresh_token(subject=user.id, company_id=user.company_id)
        return Token(access_token=new_access, refresh_token=new_refresh)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current user info (requires auth)."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        company_id=current_user.company_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.post("/logout")
async def logout():
    """Logout (client-side token removal)."""
    return {"message": "Logged out successfully"}


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset code sent to the user's email."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    # Always return success to prevent email enumeration
    if not user:
        return ForgotPasswordResponse(
            message="If the email exists, a password reset code has been sent"
        )

    # Generate 6-digit code and store with expiry
    import random

    code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.EMAIL_RESET_CODE_EXPIRE_MINUTES
    )

    user.password_reset_code = code
    user.password_reset_expires = expires_at
    await db.commit()

    # Send the code via email (dev mode logs to console + file)
    await send_reset_code(request.email, code)

    return ForgotPasswordResponse(
        message="If the email exists, a password reset code has been sent"
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a valid reset code."""
    result = await db.execute(select(User).where(User.password_reset_code == request.code))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code",
        )

    if not user.password_reset_expires or user.password_reset_expires < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset code has expired",
        )

    # Update password and clear reset code
    user.hashed_password = get_password_hash(request.new_password)
    user.password_reset_code = None
    user.password_reset_expires = None
    await db.commit()

    return ResetPasswordResponse(message="Password reset successfully")