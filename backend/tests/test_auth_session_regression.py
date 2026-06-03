"""Auth/session regression tests for staff login, /auth/me safety, and role protections."""

import os

import pytest
import requests


def _read_backend_url_from_file() -> str | None:
    env_path = "/app/frontend/.env"
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r", encoding="utf-8") as env_file:
        matches = [line.split("=", 1)[1].strip().rstrip("/") for line in env_file if line.startswith("REACT_APP_BACKEND_URL=")]
    return matches[0] if matches else None


def _get_base_url() -> str:
    base_url = os.environ.get("REACT_APP_BACKEND_URL") or _read_backend_url_from_file()
    if not base_url:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return base_url.rstrip("/")


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

    def test_logout_revokes_token_immediately(self, api_client):
        payload = login(api_client, STAFF_ACCESS_CODE)
        token = payload["token"]
        logout = api_client.post(
            f"{API_BASE}/auth/logout", headers=auth_headers(token), timeout=20
        )
        assert logout.status_code == 200
        assert logout.json().get("status") == "ok"

        me = api_client.get(f"{API_BASE}/auth/me", headers=auth_headers(token), timeout=20)
        assert me.status_code == 401
        assert "revoked" in me.json().get("detail", "").lower()

    def test_revoked_token_cannot_access_protected_route(self, api_client):
        payload = login(api_client, VIEWER_ACCESS_CODE)
        token = payload["token"]
        logout = api_client.post(
            f"{API_BASE}/auth/logout", headers=auth_headers(token), timeout=20
        )
        assert logout.status_code == 200

        dashboard = api_client.get(f"{API_BASE}/dashboard", headers=auth_headers(token), timeout=20)
        assert dashboard.status_code == 401

    def test_relogin_after_logout_returns_new_working_token(self, api_client):
        first_login = login(api_client, STAFF_ACCESS_CODE)
        first_token = first_login["token"]

        logout = api_client.post(
            f"{API_BASE}/auth/logout", headers=auth_headers(first_token), timeout=20
        )
        assert logout.status_code == 200

        second_login = login(api_client, STAFF_ACCESS_CODE)
        second_token = second_login["token"]
        assert second_token != first_token

        old_me = api_client.get(f"{API_BASE}/auth/me", headers=auth_headers(first_token), timeout=20)
        assert old_me.status_code == 401

        new_me = api_client.get(f"{API_BASE}/auth/me", headers=auth_headers(second_token), timeout=20)
        assert new_me.status_code == 200
        new_me_data = new_me.json()
        assert new_me_data["id"] == second_login["staff"]["id"]
        assert new_me_data["role"] == "staff"

    def test_admin_can_change_viewer_code_and_invalidate_viewer_sessions(self, api_client):
        admin_login = login(api_client, ADMIN_ACCESS_CODE)
        viewer_login = login(api_client, VIEWER_ACCESS_CODE)
        viewer_token = viewer_login["token"]
        temporary_code = "VIEW-TEMP-998877"

        update = api_client.patch(
            f"{API_BASE}/auth/access-codes",
            headers=auth_headers(admin_login["token"]),
            json={"role": "viewer", "new_access_code": temporary_code},
            timeout=20,
        )
        assert update.status_code == 200

        old_token_response = api_client.get(f"{API_BASE}/auth/me", headers=auth_headers(viewer_token), timeout=20)
        assert old_token_response.status_code == 401
        assert "access code" in old_token_response.json().get("detail", "").lower()

        new_viewer_login = login(api_client, temporary_code)
        assert new_viewer_login["staff"]["role"] == "viewer"

        restore = api_client.patch(
            f"{API_BASE}/auth/access-codes",
            headers=auth_headers(admin_login["token"]),
            json={"role": "viewer", "new_access_code": VIEWER_ACCESS_CODE},
            timeout=20,
        )
        assert restore.status_code == 200

    def test_non_admin_cannot_change_access_codes(self, api_client):
        staff_login = login(api_client, STAFF_ACCESS_CODE)
        update = api_client.patch(
            f"{API_BASE}/auth/access-codes",
            headers=auth_headers(staff_login["token"]),
            json={"role": "viewer", "new_access_code": "VIEW-FAIL-123"},
            timeout=20,
        )
        assert update.status_code == 403
