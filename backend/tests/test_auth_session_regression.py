"""Auth/session regression tests for staff login, /auth/me safety, and role protections."""

import os

import pytest
import requests


def _get_base_url() -> str:
    from_env = os.environ.get("REACT_APP_BACKEND_URL")
    if from_env:
        return from_env.rstrip("/")

    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    value = line.split("=", 1)[1].strip().rstrip("/")
                    if value:
                        return value

    pytest.skip("REACT_APP_BACKEND_URL is not configured")


BASE_URL = _get_base_url()
API_BASE = f"{BASE_URL}/api"
ADMIN_ACCESS_CODE = "FK-ADMIN-7X9Q2"
STAFF_ACCESS_CODE = "FK-STAFF-4M8P1"
VIEWER_ACCESS_CODE = "FK-VIEW-6L3N5"


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def login(api_client, code: str):
    response = api_client.post(
        f"{API_BASE}/auth/staff-login", json={"access_code": code}, timeout=20
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("token"), str) and data["token"].strip()
    assert isinstance(data.get("staff"), dict)
    return data


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


class TestAuthSessionRegression:
    """Staff auth login/logout + /auth/me and protected endpoint guards."""

    @pytest.mark.parametrize(
        "access_code,expected_role,expected_email",
        [
            (ADMIN_ACCESS_CODE, "admin", "admin@frontkind.app"),
            (STAFF_ACCESS_CODE, "staff", "staff@frontkind.app"),
            (VIEWER_ACCESS_CODE, "viewer", "viewer@frontkind.app"),
        ],
    )
    def test_staff_login_roles(self, api_client, access_code, expected_role, expected_email):
        payload = login(api_client, access_code)
        assert payload["staff"]["role"] == expected_role
        assert payload["staff"]["email"] == expected_email

    @pytest.mark.parametrize("access_code", [ADMIN_ACCESS_CODE, STAFF_ACCESS_CODE, VIEWER_ACCESS_CODE])
    def test_auth_me_returns_current_staff_no_runtime_crash(self, api_client, access_code):
        payload = login(api_client, access_code)
        response = api_client.get(
            f"{API_BASE}/auth/me", headers=auth_headers(payload["token"]), timeout=20
        )
        assert response.status_code == 200
        me = response.json()
        assert me["id"] == payload["staff"]["id"]
        assert me["email"] == payload["staff"]["email"]
        assert me["role"] == payload["staff"]["role"]

    def test_invalid_token_rejected_consistently(self, api_client):
        response = api_client.get(
            f"{API_BASE}/auth/me", headers=auth_headers("invalid.token.value"), timeout=20
        )
        assert response.status_code == 401
        assert "invalid" in response.json().get("detail", "").lower() or "expired" in response.json().get("detail", "").lower()

    @pytest.mark.parametrize("endpoint", ["/dashboard", "/notifications", "/appointments"])
    def test_protected_endpoints_require_valid_staff_token(self, api_client, endpoint):
        response = api_client.get(f"{API_BASE}{endpoint}", timeout=20)
        assert response.status_code == 401

    def test_logout_then_protected_call_with_same_token_is_still_well_formed(self, api_client):
        payload = login(api_client, STAFF_ACCESS_CODE)
        token = payload["token"]
        logout = api_client.post(
            f"{API_BASE}/auth/logout", headers=auth_headers(token), timeout=20
        )
        assert logout.status_code == 200
        assert logout.json().get("status") == "ok"

        # No token revocation by design; endpoint should still respond normally (no server/runtime crash)
        me = api_client.get(f"{API_BASE}/auth/me", headers=auth_headers(token), timeout=20)
        assert me.status_code in [200, 401]
        assert isinstance(me.json(), dict)
