from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status, Request
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.config import get_settings
from app.core.security import decode_token
from app.models.user import User
from app.models.company import Company

settings = get_settings()


def get_token_from_header(request: Request) -> Optional[str]:
    """Extract JWT token from Authorization header."""
    authorization: Optional[str] = request.headers.get("authorization")
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token


async def get_current_user(
    token: Optional[str] = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    
    if token is None:
        raise credentials_exception
    
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        company_id: str = payload.get("company_id")
        token_type: str = payload.get("type")
        
        if user_id is None or company_id is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    result = await db.execute(
        select(User).where(User.id == UUID(user_id), User.company_id == UUID(company_id))
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user (alias for clarity)."""
    return current_user


async def get_current_company(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Company:
    """Get current user's company."""
    result = await db.execute(
        select(Company).where(Company.id == current_user.company_id)
    )
    company = result.scalar_one_or_none()
    
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    
    return company


async def get_optional_user(
    token: Optional[str] = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current user if token is valid, otherwise return None."""
    if not token:
        return None
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None