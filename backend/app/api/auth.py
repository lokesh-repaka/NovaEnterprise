"""Authentication and token issuance API router (P3-2).

Provides endpoints for demo user discovery, direct demo token issuance,
standard JSON credential login, OAuth2 password grant form login, and
authenticated user profile inspection (/auth/me).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories.security import UserRepository
from backend.app.schemas.auth import (
    DemoTokenRequest,
    DemoUser,
    LoginRequest,
    TokenResponse,
    UserProfileResponse,
)
from backend.app.services.auth import (
    authenticate_user,
    get_demo_user_by_role,
    get_demo_users,
    issue_token_for_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/demo-users",
    response_model=list[DemoUser],
    summary="List predefined demo users",
    description="Returns available demo accounts across all three RBAC roles (admin, analyst, viewer).",
)
def list_demo_users() -> list[DemoUser]:
    """Retrieve all available demo users."""
    return get_demo_users()


@router.post(
    "/demo-token",
    response_model=TokenResponse,
    summary="Issue JWT token for a demo role",
    description="Directly issues a signed JWT access token for the specified demo role without requiring credentials.",
)
def issue_demo_token(payload: DemoTokenRequest) -> TokenResponse:
    """Issue a demo access token for rapid evaluation and testing."""
    demo_user = get_demo_user_by_role(payload.role)
    if demo_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No demo user configured for role: {payload.role.value}",
        )

    return issue_token_for_user(
        user_id=demo_user.id,
        username=demo_user.username,
        email=demo_user.email,
        role=demo_user.role,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with credentials",
    description="Validates username or email with password against the database and issues a signed JWT.",
)
def login(
    credentials: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate user with username/email and password."""
    user = authenticate_user(
        db=db,
        username_or_email=credentials.username_or_email,
        password=credentials.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return issue_token_for_user(
        user_id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
    )


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="OAuth2 password form login",
    description="OAuth2-compatible endpoint for token issuance via form submission.",
)
def oauth2_login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """OAuth2 password grant endpoint."""
    user = authenticate_user(
        db=db,
        username_or_email=form_data.username,
        password=form_data.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return issue_token_for_user(
        user_id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
    description="Returns the profile information for the authenticated user from the Bearer token.",
)
def get_current_user_profile(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserProfileResponse:
    """Return identity profile of the currently authenticated user."""
    repo = UserRepository(db)
    user = repo.get(current_user.id)
    if user is not None:
        return UserProfileResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=True,
            created_at=user.created_at,
        )

    # Fallback to claims in the validated JWT token
    return UserProfileResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
    )
