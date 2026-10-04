from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import bcrypt
import jwt
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import ErrorCode
from config.settings import get_settings
from contracts.auth import LoginRequest, RegisterRequest
from middleware.error_handler import ApplicationError
from models.user import User
from repositories.user_db import create_user, get_user_by_email, get_user_by_id


settings = get_settings()
DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"invalid-password", bcrypt.gensalt())


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def create_access_token(user: User) -> tuple[str, int]:
    expires_in = settings.jwt_access_token_minutes * 60
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
            "jti": str(uuid4()),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_in


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except InvalidTokenError as error:
        raise ApplicationError(
            error_code=ErrorCode.UNAUTHORIZED,
            message="The access token is invalid or expired.",
            status_code=401,
        ) from error

    user_id = payload.get("sub")
    if payload.get("type") != "access" or not isinstance(user_id, str):
        raise ApplicationError(
            error_code=ErrorCode.UNAUTHORIZED,
            message="The access token is invalid.",
            status_code=401,
        )
    return user_id


async def register_user(session: AsyncSession, request: RegisterRequest) -> User:
    email = normalize_email(request.email)
    if await get_user_by_email(session, email) is not None:
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="An account with this email already exists.",
            status_code=409,
        )

    password_bytes = request.password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ApplicationError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Password cannot exceed 72 encoded bytes.",
            status_code=422,
        )
    password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")
    user = await create_user(
        session,
        email=email,
        display_name=request.display_name.strip(),
        password_hash=password_hash,
    )
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, request: LoginRequest) -> User:
    user = await get_user_by_email(session, normalize_email(request.email))
    stored_hash = user.password_hash.encode("utf-8") if user else DUMMY_PASSWORD_HASH
    password_bytes = request.password.encode("utf-8")
    password_valid = len(password_bytes) <= 72 and bcrypt.checkpw(password_bytes, stored_hash)
    if user is None or not password_valid or not user.is_active:
        raise ApplicationError(
            error_code=ErrorCode.UNAUTHORIZED,
            message="Email or password is incorrect.",
            status_code=401,
        )
    return user


async def get_active_user(session: AsyncSession, user_id: str) -> User:
    try:
        parsed_user_id = UUID(user_id)
    except ValueError as error:
        raise ApplicationError(
            error_code=ErrorCode.UNAUTHORIZED,
            message="The access token is invalid.",
            status_code=401,
        ) from error
    user = await get_user_by_id(session, parsed_user_id)
    if user is None or not user.is_active:
        raise ApplicationError(
            error_code=ErrorCode.UNAUTHORIZED,
            message="The account is unavailable.",
            status_code=401,
        )
    return user
