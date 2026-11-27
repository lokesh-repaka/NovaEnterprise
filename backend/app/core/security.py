"""Security, JWT authentication, and RBAC authorization guards for NovaEnterprise.

Enforces role-based permissions (viewer, analyst, admin) via FastAPI dependencies,
manages JWT token issuance and verification, and provides secure password hashing.
"""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from backend.app.core.config import get_settings


class Role(str, Enum):
    """System role hierarchy definitions."""

    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMIN = "admin"


# Role hierarchy numerical weights (Higher number = broader access)
ROLE_HIERARCHY: dict[str, int] = {
    Role.VIEWER.value: 1,
    Role.ANALYST.value: 2,
    Role.ADMIN.value: 3,
}


class AuthenticatedUser(BaseModel):
    """Identity context for authenticated client requests."""

    id: str
    username: str
    email: str
    role: str
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


# Standard HTTP Bearer scheme
bearer_scheme = HTTPBearer(auto_error=False)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt with a generated salt."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Issue a signed JWT access token containing identity claims and expiration."""
    settings = get_settings()
    to_encode = data.copy()

    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire, "iat": now})

    encoded_jwt: str = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token against the configured secret key.

    Raises HTTPException 401 if the token has expired, has an invalid signature,
    or cannot be decoded.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> AuthenticatedUser:
    """FastAPI dependency to extract and validate the current authenticated user from Bearer token."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme: Bearer required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = AuthenticatedUser(
        id=str(user_id),
        username=str(payload.get("username", user_id)),
        email=str(payload.get("email", "")),
        role=str(payload.get("role", Role.VIEWER.value)).lower(),
        is_active=bool(payload.get("is_active", True)),
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def require_role(
    *allowed_roles: str | Role,
) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """FastAPI dependency factory enforcing Role-Based Access Control (RBAC).

    Supports role hierarchy:
      - 'viewer' endpoints can be accessed by viewer, analyst, and admin.
      - 'analyst' endpoints can be accessed by analyst and admin.
      - 'admin' endpoints can be accessed strictly by admin.

    Raises HTTPException 403 Forbidden if user lacks sufficient privileges.
    """
    normalized_allowed = [
        r.value.lower() if isinstance(r, Role) else str(r).lower()
        for r in allowed_roles
    ]

    def role_checker(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        user_role = current_user.role.lower()

        # Admin superuser bypass
        if user_role == Role.ADMIN.value:
            return current_user

        # Direct match check
        if user_role in normalized_allowed:
            return current_user

        # Hierarchical level check: If any allowed role is <= current_user level
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        can_access = False
        for required in normalized_allowed:
            required_level = ROLE_HIERARCHY.get(required, 999)
            if user_level >= required_level:
                can_access = True
                break

        if not can_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Operation requires one of the following roles: {normalized_allowed}",
            )

        return current_user

    return role_checker
