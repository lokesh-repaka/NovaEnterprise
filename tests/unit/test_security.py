"""Unit tests for JWT authentication, RBAC, and require_role guards (P3-1).

Validates password hashing, token encoding/decoding, expiration handling,
FastAPI dependency injection, and hierarchical role-based access control.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
import pytest
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.core.security import (
    AuthenticatedUser,
    Role,
    create_access_token,
    decode_access_token,
    get_current_user,
    get_password_hash,
    require_role,
    verify_password,
)


def test_password_hashing():
    """Verify password hashing and timing-attack resistant verification."""
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(password, "") is False
    assert verify_password("test", "corrupt-invalid-hash") is False


def test_token_creation_and_decoding():
    """Verify JWT access token generation and claims payload decoding."""
    user_payload = {
        "sub": "usr-123",
        "username": "analyst_alice",
        "email": "alice@nova.io",
        "role": "analyst",
    }

    token = create_access_token(user_payload, expires_delta=timedelta(minutes=15))
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded["sub"] == "usr-123"
    assert decoded["username"] == "analyst_alice"
    assert decoded["email"] == "alice@nova.io"
    assert decoded["role"] == "analyst"
    assert "exp" in decoded
    assert "iat" in decoded


def test_expired_token_handling():
    """Verify that expired tokens raise 401 Unauthorized."""
    settings = get_settings()
    expired_payload = {
        "sub": "usr-123",
        "username": "analyst_alice",
        "email": "alice@nova.io",
        "role": "analyst",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=10),
        "iat": datetime.now(timezone.utc) - timedelta(minutes=20),
    }

    expired_token = jwt.encode(
        expired_payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(Exception) as exc_info:
        decode_access_token(expired_token)
    assert (
        "expired" in str(exc_info.value).lower()
        or getattr(exc_info.value, "status_code", None) == 401
    )


def test_invalid_signature_and_malformed_token():
    """Verify that tampering with token signatures or malformed tokens fail validation."""
    settings = get_settings()
    user_payload = {"sub": "usr-123", "role": "analyst"}

    # Token signed with wrong secret key (using >= 32 byte secret to avoid HMAC warning)
    tampered_token = jwt.encode(
        user_payload,
        "wrong-secret-key-that-is-at-least-32-bytes-long",
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(Exception) as exc_info:
        decode_access_token(tampered_token)
    assert (
        getattr(exc_info.value, "status_code", None) == 401
        or "signature" in str(exc_info.value).lower()
    )

    # Completely malformed token
    with pytest.raises(Exception) as exc_info2:
        decode_access_token("not-a-valid-jwt-token")
    assert (
        getattr(exc_info2.value, "status_code", None) == 401
        or "invalid" in str(exc_info2.value).lower()
    )


# Create miniature test FastAPI application for route dependency verification
rbac_app = FastAPI()

viewer_guard = require_role(Role.VIEWER)
analyst_guard = require_role(Role.ANALYST)
admin_guard = require_role(Role.ADMIN)


@rbac_app.get("/test/viewer")
def viewer_endpoint(user: Annotated[AuthenticatedUser, Depends(viewer_guard)]):
    return {"status": "ok", "role": user.role, "user": user.username}


@rbac_app.get("/test/analyst")
def analyst_endpoint(user: Annotated[AuthenticatedUser, Depends(analyst_guard)]):
    return {"status": "ok", "role": user.role, "user": user.username}


@rbac_app.get("/test/admin")
def admin_endpoint(user: Annotated[AuthenticatedUser, Depends(admin_guard)]):
    return {"status": "ok", "role": user.role, "user": user.username}


@rbac_app.get("/test/any-authenticated")
def any_auth_endpoint(user: Annotated[AuthenticatedUser, Depends(get_current_user)]):
    return {"status": "ok", "username": user.username}


def test_rbac_endpoint_access_matrix():
    """Verify RBAC access matrix across viewer, analyst, and admin roles.

    Viewer: Allowed viewer endpoints only. 403 on analyst & admin endpoints.
    Analyst: Allowed viewer & analyst endpoints. 403 on admin endpoints.
    Admin: Allowed all endpoints (viewer, analyst, admin).
    """
    client = TestClient(rbac_app)

    viewer_token = create_access_token(
        {"sub": "usr-v", "username": "v_user", "email": "v@nova.io", "role": "viewer"}
    )
    analyst_token = create_access_token(
        {"sub": "usr-a", "username": "a_user", "email": "a@nova.io", "role": "analyst"}
    )
    admin_token = create_access_token(
        {
            "sub": "usr-adm",
            "username": "admin_user",
            "email": "admin@nova.io",
            "role": "admin",
        }
    )

    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Unauthenticated requests -> 401 Unauthorized
    assert client.get("/test/viewer").status_code == status.HTTP_401_UNAUTHORIZED
    assert client.get("/test/analyst").status_code == status.HTTP_401_UNAUTHORIZED
    assert client.get("/test/admin").status_code == status.HTTP_401_UNAUTHORIZED
    assert (
        client.get("/test/any-authenticated").status_code
        == status.HTTP_401_UNAUTHORIZED
    )

    # 2. Viewer Access Permissions
    # Viewer -> /test/viewer: 200 OK
    resp_v_v = client.get("/test/viewer", headers=viewer_headers)
    assert resp_v_v.status_code == status.HTTP_200_OK
    assert resp_v_v.json()["role"] == "viewer"

    # Viewer -> /test/analyst: 403 Forbidden (F1 / Claude.md §2)
    resp_v_a = client.get("/test/analyst", headers=viewer_headers)
    assert resp_v_a.status_code == status.HTTP_403_FORBIDDEN
    assert (
        "Forbidden" in resp_v_a.json()["detail"]
        or "permitted" in resp_v_a.json()["detail"].lower()
    )

    # Viewer -> /test/admin: 403 Forbidden
    resp_v_adm = client.get("/test/admin", headers=viewer_headers)
    assert resp_v_adm.status_code == status.HTTP_403_FORBIDDEN

    # 3. Analyst Access Permissions
    # Analyst -> /test/viewer: 200 OK (Hierarchy)
    resp_a_v = client.get("/test/viewer", headers=analyst_headers)
    assert resp_a_v.status_code == status.HTTP_200_OK

    # Analyst -> /test/analyst: 200 OK
    resp_a_a = client.get("/test/analyst", headers=analyst_headers)
    assert resp_a_a.status_code == status.HTTP_200_OK
    assert resp_a_a.json()["role"] == "analyst"

    # Analyst -> /test/admin: 403 Forbidden (F17 / Claude.md §2)
    resp_a_adm = client.get("/test/admin", headers=analyst_headers)
    assert resp_a_adm.status_code == status.HTTP_403_FORBIDDEN

    # 4. Admin Access Permissions (Superuser privileges across all routes)
    # Admin -> /test/viewer: 200 OK
    assert (
        client.get("/test/viewer", headers=admin_headers).status_code
        == status.HTTP_200_OK
    )

    # Admin -> /test/analyst: 200 OK
    assert (
        client.get("/test/analyst", headers=admin_headers).status_code
        == status.HTTP_200_OK
    )

    # Admin -> /test/admin: 200 OK
    resp_adm_adm = client.get("/test/admin", headers=admin_headers)
    assert resp_adm_adm.status_code == status.HTTP_200_OK
    assert resp_adm_adm.json()["role"] == "admin"


def test_invalid_bearer_format():
    """Verify non-Bearer auth headers or corrupt token formats are rejected."""
    client = TestClient(rbac_app)

    # Missing credentials
    assert client.get("/test/viewer").status_code == status.HTTP_401_UNAUTHORIZED

    # Invalid scheme (Basic instead of Bearer)
    from fastapi.security import HTTPAuthorizationCredentials

    with pytest.raises(Exception) as exc_scheme:
        get_current_user(
            HTTPAuthorizationCredentials(scheme="Basic", credentials="xyz")
        )
    assert exc_scheme.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid authentication scheme" in exc_scheme.value.detail

    # Missing 'Bearer ' prefix
    assert (
        client.get("/test/viewer", headers={"Authorization": "Token 12345"}).status_code
        == status.HTTP_401_UNAUTHORIZED
    )

    # Empty bearer
    assert (
        client.get("/test/viewer", headers={"Authorization": "Bearer "}).status_code
        == status.HTTP_401_UNAUTHORIZED
    )

    # Missing subject claim
    settings = get_settings()
    no_sub_token = jwt.encode(
        {"role": "viewer"}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    assert (
        client.get(
            "/test/viewer", headers={"Authorization": f"Bearer {no_sub_token}"}
        ).status_code
        == status.HTTP_401_UNAUTHORIZED
    )

    # Inactive user token
    inactive_token = jwt.encode(
        {"sub": "usr-inactive", "role": "viewer", "is_active": False},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert (
        client.get(
            "/test/viewer", headers={"Authorization": f"Bearer {inactive_token}"}
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )
