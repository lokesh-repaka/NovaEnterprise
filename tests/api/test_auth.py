"""Integration and route tests for Auth and Demo Token endpoints (P3-2).

Verifies demo user discovery, direct demo token issuance, standard credential
login, OAuth2 form login, and the authenticated /auth/me user profile endpoint.
"""

from fastapi.testclient import TestClient

from backend.app.core.db import get_engine, init_db
from backend.app.core.security import decode_access_token
from backend.app.main import create_app


def setup_module():
    """Ensure in-memory SQLite schema is populated before testing API routes."""
    engine = get_engine()
    init_db(engine)


def test_demo_users_list():
    """Test GET /api/v1/auth/demo-users returns predefined demo accounts."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/demo-users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3

        roles = [u["role"] for u in data]
        assert "admin" in roles
        assert "analyst" in roles
        assert "viewer" in roles

        for user in data:
            assert "id" in user
            assert "username" in user
            assert "email" in user
            assert "role" in user
            assert "name" in user
            assert "description" in user


def test_demo_token_issuance():
    """Test POST /api/v1/auth/demo-token issues valid JWT for all three roles."""
    app = create_app()
    with TestClient(app) as client:
        for target_role in ["admin", "analyst", "viewer"]:
            response = client.post(
                "/api/v1/auth/demo-token",
                json={"role": target_role},
            )
            assert response.status_code == 200, response.text
            payload = response.json()

            assert "access_token" in payload
            assert payload["token_type"].lower() == "bearer"
            assert payload["role"] == target_role
            assert payload["expires_in"] > 0
            assert "user_id" in payload
            assert "email" in payload
            assert "username" in payload

            # Verify cryptographic signature and claims
            claims = decode_access_token(payload["access_token"])
            assert claims["sub"] == payload["user_id"]
            assert claims["role"] == target_role
            assert claims["email"] == payload["email"]


def test_demo_token_invalid_role():
    """Test POST /api/v1/auth/demo-token rejects unapproved roles with 422."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/demo-token",
            json={"role": "superuser"},
        )
        assert response.status_code in (400, 422)


def test_login_standard_credentials():
    """Test POST /api/v1/auth/login authenticates via username/email and password."""
    app = create_app()
    with TestClient(app) as client:
        # 1. Login with demo username
        response = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "analyst", "password": "demo_password"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["role"] == "analyst"
        assert "access_token" in body

        # 2. Login with demo email
        response_email = client.post(
            "/api/v1/auth/login",
            json={
                "username_or_email": "analyst@novaenterprise.io",
                "password": "demo_password",
            },
        )
        assert response_email.status_code == 200
        assert response_email.json()["role"] == "analyst"

        # 3. Invalid password
        bad_pw = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "analyst", "password": "wrong_password"},
        )
        assert bad_pw.status_code == 401
        assert "Invalid" in bad_pw.json()["detail"]

        # 4. Unknown user
        unknown = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "nonexistent_user", "password": "any"},
        )
        assert unknown.status_code == 401


def test_oauth2_form_token_endpoint():
    """Test POST /api/v1/auth/token standard OAuth2 form submission."""
    app = create_app()
    with TestClient(app) as client:
        # 1. Valid credentials
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "admin", "password": "demo_password"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert data["role"] == "admin"
        assert "access_token" in data

        # 2. Invalid credentials via form
        bad_res = client.post(
            "/api/v1/auth/token",
            data={"username": "admin", "password": "wrong_password"},
        )
        assert bad_res.status_code == 401
        assert "Invalid" in bad_res.json()["detail"]


def test_get_current_user_profile():
    """Test GET /api/v1/auth/me returns current user identity."""
    app = create_app()
    with TestClient(app) as client:
        # Missing token
        unauth = client.get("/api/v1/auth/me")
        assert unauth.status_code == 401

        # Issue demo token for admin
        token_res = client.post(
            "/api/v1/auth/demo-token",
            json={"role": "admin"},
        )
        token = token_res.json()["access_token"]

        # Authenticated request
        me_res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["username"] == "admin"
        assert me_data["role"] == "admin"
        assert me_data["email"] == "admin@novaenterprise.io"
        assert me_data["is_active"] is True


def test_get_current_user_profile_expired_and_invalid_token():
    """Test /api/v1/auth/me rejects expired and tampered tokens with 401."""
    from datetime import timedelta

    from backend.app.core.security import create_access_token

    app = create_app()
    with TestClient(app) as client:
        # 1. Expired token
        expired_token = create_access_token(
            {"sub": "usr-admin-01", "role": "admin", "username": "admin"},
            expires_delta=timedelta(seconds=-10),
        )
        res_expired = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert res_expired.status_code == 401
        assert "expired" in res_expired.json()["detail"].lower()

        # 2. Tampered token
        res_tampered = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}corrupted"},
        )
        assert res_tampered.status_code == 401

        # 3. Valid token for user not present in SQL users table (token fallback)
        synth_token = create_access_token(
            {
                "sub": "usr-synthetic-999",
                "username": "synthetic",
                "email": "synthetic@example.com",
                "role": "analyst",
                "is_active": True,
            }
        )
        res_synth = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {synth_token}"},
        )
        assert res_synth.status_code == 200
        synth_data = res_synth.json()
        assert synth_data["id"] == "usr-synthetic-999"
        assert synth_data["username"] == "synthetic"
        assert synth_data["role"] == "analyst"


def test_seed_demo_users_idempotence():
    """Verify seed_demo_users service function executes idempotently."""
    from backend.app.core.db import get_engine, get_session_factory
    from backend.app.services.auth import (
        get_demo_user_by_role,
        seed_demo_users,
    )

    engine = get_engine()
    session_factory = get_session_factory(engine)
    with session_factory() as db:
        users1 = seed_demo_users(db)
        assert len(users1) == 3

        users2 = seed_demo_users(db)
        assert len(users2) == 3
        assert {u.role for u in users2} == {"admin", "analyst", "viewer"}

    # Test get_demo_user_by_role
    admin = get_demo_user_by_role("admin")
    assert admin is not None
    assert admin.username == "admin"

    unknown = get_demo_user_by_role("nonexistent_role")
    assert unknown is None
