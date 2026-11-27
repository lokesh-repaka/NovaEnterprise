"""Authentication and token request/response schemas (P3-2).

Codifies Pydantic v2 data models for demo user discovery, token issuance,
standard credential login, and user profiles.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.security import Role


class DemoUser(BaseModel):
    """Metadata for predefined enterprise demo accounts."""

    id: str
    username: str
    email: str
    role: Role
    name: str
    description: str

    model_config = ConfigDict(from_attributes=True)


class DemoTokenRequest(BaseModel):
    """Request payload for direct demo token issuance."""

    role: Role = Field(
        ...,
        description="Target demo role: admin, analyst, or viewer",
    )


class LoginRequest(BaseModel):
    """Request payload for credential-based authentication."""

    username_or_email: str = Field(
        ...,
        min_length=1,
        description="Username or registered email address",
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Plaintext account password",
    )


class TokenResponse(BaseModel):
    """OAuth2-compatible Bearer access token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    user_id: str
    email: str
    username: str


class UserProfileResponse(BaseModel):
    """Authenticated user profile representation."""

    id: str
    username: str
    email: str
    role: str
    is_active: bool = True
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
