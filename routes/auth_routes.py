from fastapi import APIRouter, status

from contracts.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from routes.route_helpers import ActorId, DatabaseSession
from services.auth_actions import (
    authenticate_user,
    create_access_token,
    get_active_user,
    register_user,
)


router = APIRouter(prefix="/auth", tags=["authentication"])


def token_response(user) -> TokenResponse:
    token, expires_in = create_access_token(user)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_route(body: RegisterRequest, session: DatabaseSession) -> TokenResponse:
    return token_response(await register_user(session, body))


@router.post("/login", response_model=TokenResponse)
async def login_route(body: LoginRequest, session: DatabaseSession) -> TokenResponse:
    return token_response(await authenticate_user(session, body))


@router.get("/me", response_model=UserResponse)
async def me_route(actor_id: ActorId, session: DatabaseSession) -> UserResponse:
    return UserResponse.model_validate(await get_active_user(session, actor_id))
