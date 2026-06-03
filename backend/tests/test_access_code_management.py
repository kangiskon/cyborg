"""Regression tests for admin-managed staff/viewer access-code updates and session invalidation."""

import os
import uuid

import pytest
import requests


def _read_backend_url_from_file() -> str | None:
    env_path = "/app/frontend/.env"
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r", encoding="utf-8") as env_file:
        matches = [
            line.split("=", 1)[1].strip().rstrip("/")
            for line in env_file
            if line.startswith("REACT_APP_BACKEND_URL=")
        ]
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


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def login(api_client, access_code: str):
    response = api_client.post(
        f"{API_BASE}/auth/staff-login", json={"access_code": access_code}, timeout=20
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("token"), str) and data["token"].strip()
    assert isinstance(data.get("staff"), dict)
    return data


def update_access_code(api_client, admin_token: str, role: str, new_code: str):
    return api_client.patch(
        f"{API_BASE}/auth/access-codes",
        headers=auth_headers(admin_token),
        json={"role": role, "new_access_code": new_code},
        timeout=20,
    )


@pytest.fixture(scope="module", autouse=True)
def restore_default_access_codes():
    """Keep staff/viewer test credentials stable across runs."""
    yield
    cleanup_client = requests.Session()
    cleanup_client.headers.update({"Content-Type": "application/json"})
    login_response = cleanup_client.post(
        f"{API_BASE}/auth/staff-login",
        json={"access_code": ADMIN_ACCESS_CODE},
        timeout=20,
    )
    if login_response.status_code != 200:
        return
    admin_token = login_response.json().get("token")
    if not admin_token:
        return
    for role, default_code in (("staff", STAFF_ACCESS_CODE), ("viewer", VIEWER_ACCESS_CODE)):
        cleanup_client.patch(
            f"{API_BASE}/auth/access-codes",
            headers=auth_headers(admin_token),
            json={"role": role, "new_access_code": default_code},
            timeout=20,
        )


class TestAccessCodeManagement:
    """Admin access-code update contract + auth regression coverage."""

    def test_admin_updates_staff_code_and_old_code_fails(self, api_client):
        admin_login = login(api_client, ADMIN_ACCESS_CODE)
        old_staff_token = login(api_client, STAFF_ACCESS_CODE)["token"]
        temporary_code = f"STAFF-TEMP-{uuid.uuid4().hex[:8]}"

        update = update_access_code(api_client, admin_login["token"], "staff", temporary_code)
        assert update.status_code == 200
        body = update.json()
        assert body["role"] == "staff"
        assert "invalidated" in body["message"].lower()

        old_me = api_client.get(
            f"{API_BASE}/auth/me", headers=auth_headers(old_staff_token), timeout=20
        )
        assert old_me.status_code == 401
        assert "access code" in old_me.json().get("detail", "").lower()

        old_login = api_client.post(
            f"{API_BASE}/auth/staff-login", json={"access_code": STAFF_ACCESS_CODE}, timeout=20
        )
        assert old_login.status_code == 401

        new_login = login(api_client, temporary_code)
        assert new_login["staff"]["role"] == "staff"

        restore = update_access_code(api_client, admin_login["token"], "staff", STAFF_ACCESS_CODE)
        assert restore.status_code == 200

    def test_admin_updates_viewer_code_and_old_code_fails(self, api_client):
        admin_login = login(api_client, ADMIN_ACCESS_CODE)
        old_viewer_token = login(api_client, VIEWER_ACCESS_CODE)["token"]
        temporary_code = f"VIEW-TEMP-{uuid.uuid4().hex[:8]}"

        update = update_access_code(api_client, admin_login["token"], "viewer", temporary_code)
        assert update.status_code == 200
        body = update.json()
        assert body["role"] == "viewer"
        assert "invalidated" in body["message"].lower()

        old_me = api_client.get(
            f"{API_BASE}/auth/me", headers=auth_headers(old_viewer_token), timeout=20
        )
        assert old_me.status_code == 401
        assert "access code" in old_me.json().get("detail", "").lower()

        old_login = api_client.post(
            f"{API_BASE}/auth/staff-login", json={"access_code": VIEWER_ACCESS_CODE}, timeout=20
        )
        assert old_login.status_code == 401

        new_login = login(api_client, temporary_code)
        assert new_login["staff"]["role"] == "viewer"

        restore = update_access_code(api_client, admin_login["token"], "viewer", VIEWER_ACCESS_CODE)
        assert restore.status_code == 200

    def test_non_admin_cannot_change_access_codes(self, api_client):
        staff_login = login(api_client, STAFF_ACCESS_CODE)
        response = api_client.patch(
            f"{API_BASE}/auth/access-codes",
            headers=auth_headers(staff_login["token"]),
            json={"role": "viewer", "new_access_code": "VIEW-BLOCK-123"},
            timeout=20,
        )
        assert response.status_code == 403

    def test_admin_cannot_change_admin_code_via_endpoint(self, api_client):
        admin_login = login(api_client, ADMIN_ACCESS_CODE)
        response = api_client.patch(
            f"{API_BASE}/auth/access-codes",
            headers=auth_headers(admin_login["token"]),
            json={"role": "admin", "new_access_code": "ADMIN-NEW-123"},
            timeout=20,
        )
        assert response.status_code == 422
        detail = response.json().get("detail", [])
        text = " ".join(item.get("msg", "") for item in detail if isinstance(item, dict)).lower()
        assert "only staff and viewer" in text

    def test_audit_log_contains_access_code_update_entry(self, api_client):
        admin_login = login(api_client, ADMIN_ACCESS_CODE)
        temporary_code = f"STAFF-AUDIT-{uuid.uuid4().hex[:8]}"

        update = update_access_code(api_client, admin_login["token"], "staff", temporary_code)
        assert update.status_code == 200

        logs_response = api_client.get(
            f"{API_BASE}/audit-logs",
            headers=auth_headers(admin_login["token"]),
            params={"action": "access_code_update", "actor_role": "all"},
            timeout=20,
        )
        assert logs_response.status_code == 200
        logs = logs_response.json().get("logs", [])
        assert any(log.get("action") == "access_code_update" for log in logs)

        restore = update_access_code(api_client, admin_login["token"], "staff", STAFF_ACCESS_CODE)
        assert restore.status_code == 200

    def test_notification_center_includes_staff_security_notification(self, api_client):
        admin_login = login(api_client, ADMIN_ACCESS_CODE)
        temporary_code = f"VIEW-NOTIF-{uuid.uuid4().hex[:8]}"

        update = update_access_code(api_client, admin_login["token"], "viewer", temporary_code)
        assert update.status_code == 200

        notifications_response = api_client.get(
            f"{API_BASE}/notifications",
            headers=auth_headers(admin_login["token"]),
            params={"type": "staff_security", "status": "all"},
            timeout=20,
        )
        assert notifications_response.status_code == 200
        payload = notifications_response.json()
        notifications = payload.get("notifications", [])
        assert any(item.get("type") == "staff_security" for item in notifications)

        restore = update_access_code(api_client, admin_login["token"], "viewer", VIEWER_ACCESS_CODE)
        assert restore.status_code == 200

    def test_existing_staff_auth_and_public_flows_still_work(self, api_client):
        staff_login = login(api_client, STAFF_ACCESS_CODE)
        me_response = api_client.get(
            f"{API_BASE}/auth/me", headers=auth_headers(staff_login["token"]), timeout=20
        )
        assert me_response.status_code == 200
        assert me_response.json().get("role") == "staff"

        logout_response = api_client.post(
            f"{API_BASE}/auth/logout", headers=auth_headers(staff_login["token"]), timeout=20
        )
        assert logout_response.status_code == 200
        assert logout_response.json().get("status") == "ok"

        lead_response = api_client.post(
            f"{API_BASE}/leads",
            json={
                "name": "TEST AccessCode Public Lead",
                "phone": "1234567890",
                "interest": "Need callback after code update test",
            },
            timeout=20,
        )
        assert lead_response.status_code == 200
        lead = lead_response.json()
        assert lead.get("name") == "TEST AccessCode Public Lead"
        assert lead.get("status") == "new"
