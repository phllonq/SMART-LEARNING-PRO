from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.auth.models import User, UserRole
from app.modules.auth.schemas import RegisterRequest
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.exceptions import DuplicateEntityException, InvalidCredentialsException


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    query = select(User).where(User.email == email.lower().strip())
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, req: RegisterRequest) -> User:
    # Check if user already exists
    existing = await get_user_by_email(db, req.email)
    if existing:
        raise DuplicateEntityException(f"Tài khoản với email '{req.email}' đã tồn tại trong hệ thống.")

    user = User(
        email=req.email.lower().strip(),
        hashed_password=hash_password(req.password),
        full_name=req.full_name.strip(),
        role=req.role.value if isinstance(req.role, UserRole) else str(req.role),
        grade_level=req.grade_level if req.role == UserRole.STUDENT else None,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, plain_password: str) -> User:
    user = await get_user_by_email(db, email)
    if not user:
        raise InvalidCredentialsException("Email hoặc mật khẩu không chính xác.")
    
    if not verify_password(plain_password, user.hashed_password):
        raise InvalidCredentialsException("Email hoặc mật khẩu không chính xác.")
        
    if not user.is_active:
        raise InvalidCredentialsException("Tài khoản của bạn đã bị vô hiệu hóa.")
        
    return user


def generate_tokens(user: User):
    token_payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "name": user.full_name
    }
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    return access_token, refresh_token
