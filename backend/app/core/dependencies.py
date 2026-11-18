from typing import AsyncGenerator, Optional, List
from fastapi import Depends, Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import InvalidCredentialsException, PermissionDeniedException
from app.modules.auth.models import User, UserRole

# HTTP Bearer for optional header-based token
security_bearer = HTTPBearer(auto_error=False)


async def get_token_from_request(
    request: Request,
    bearer_auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Optional[str]:
    """Extract JWT token. Authorization Bearer header takes precedence over HttpOnly cookie."""
    # 1. Check Authorization Bearer header first (allows API clients / mobile / overrides)
    if bearer_auth and bearer_auth.credentials:
        return bearer_auth.credentials

    # 2. Check HttpOnly Cookie
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        # Strip "Bearer " prefix if present in cookie
        if cookie_token.startswith("Bearer "):
            return cookie_token[7:]
        return cookie_token

    return None


async def get_current_user(
    token: Optional[str] = Depends(get_token_from_request),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Validate token and fetch current active user."""
    if not token:
        raise InvalidCredentialsException("Authentication required. Please log in.")

    try:
        payload = decode_token(token)
        user_id: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")
        if not user_id or token_type != "access":
            raise InvalidCredentialsException("Invalid token type or missing subject.")
    except Exception as e:
        raise InvalidCredentialsException(f"Invalid token: {str(e)}")

    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise InvalidCredentialsException("User associated with this token does not exist.")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support."
        )

    return user


def require_roles(*allowed_roles: UserRole):
    """RBAC Dependency: Require current user to have one of the specified roles."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        allowed_values = [r.value if isinstance(r, UserRole) else r for r in allowed_roles]
        if current_user.role not in allowed_values and current_user.role != UserRole.SUPERADMIN.value:
            raise PermissionDeniedException(
                f"Action restricted. Required roles: {allowed_values}. Your role: {current_user.role}"
            )
        return current_user

    return role_checker
