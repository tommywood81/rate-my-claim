"""Authentication request and response DTOs."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration payload."""

    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    """Credentials for session creation."""

    username: str
    password: str


class TokenPairResponse(BaseModel):
    """Issued tokens (also mirrored in cookies)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserPublicResponse(BaseModel):
    """Public user profile fields."""

    id: UUID
    username: str
    email: str
    role: str
    reputation_score: float

    model_config = {"from_attributes": True}
