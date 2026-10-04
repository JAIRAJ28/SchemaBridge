from uuid import UUID

from pydantic import ConfigDict, EmailStr, Field, field_validator

from contracts.page import StrictContract


class RegisterRequest(StrictContract):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be blank.")
        return value


class LoginRequest(StrictContract):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    email: str
    display_name: str
    is_active: bool


class TokenResponse(StrictContract):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
