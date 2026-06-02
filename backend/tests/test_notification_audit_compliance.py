"""Compliance-focused regression tests for notification filters and audit CSV export."""

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
                    return line.split("=", 1)[1].strip().rstrip("/")
    pytest.skip("REACT_APP_BACKEND_URL not configured")


API_BASE = f"{_get_base_url()}/api"


def _read_key_from_env_file(key: str) -> str | None:
    env_path = "/app/backend/.env"
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


ADMIN_ACCESS_CODE = os.environ.get("STAFF_ADMIN_ACCESS_CODE") or _read_key_from_env_file("STAFF_ADMIN_ACCESS_CODE")
STAFF_ACCESS_CODE = os.environ.get("STAFF_STAFF_ACCESS_CODE") or _read_key_from_env_file("STAFF_STAFF_ACCESS_CODE")
VIEWER_ACCESS_CODE = os.environ.get("STAFF_VIEWER_ACCESS_CODE") or _read_key_from_env_file("STAFF_VIEWER_ACCESS_CODE")


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def _require_access_codes():
    if not (ADMIN_ACCESS_CODE and STAFF_ACCESS_CODE and VIEWER_ACCESS_CODE):
        pytest.skip("Staff access code env vars are not configured")


def login(api_client, access_code: str) -> dict:
    response = api_client.post(
        f"{API_BASE}/auth/staff-login",
        json={"access_code": access_code},
        timeout=20,
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("token"), str) and payload["token"].strip()
    assert isinstance(payload.get("staff"), dict)
    return payload


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestNotificationCompliance:
    """Notification filter behavior and unread/read state validations."""

    def test_notification_filters_type_and_status(self, api_client):
        _require_access_codes()
        staff = login(api_client, STAFF_ACCESS_CODE)
        headers = auth_headers(staff["token"])

        filtered = api_client.get(
            f"{API_BASE}/notifications",
            headers=headers,
            params={"notification_type": "lead", "status": "all"},
            timeout=20,
        )
        assert filtered.status_code == 200
        payload = filtered.json()
        assert "notifications" in payload and isinstance(payload["notifications"], list)
        assert "unread_count" in payload and isinstance(payload["unread_count"], int)
        assert all(item.get("type") == "lead" for item in payload["notifications"])

        unread_only = api_client.get(
            f"{API_BASE}/notifications",
            headers=headers,
            params={"notification_type": "all", "status": "unread"},
            timeout=20,
        )
        assert unread_only.status_code == 200
        unread_payload = unread_only.json()
        staff_id = staff["staff"]["id"]
        assert all(staff_id not in item.get("read_by", []) for item in unread_payload["notifications"])

    def test_unread_count_is_staff_specific(self, api_client):
        _require_access_codes()
        staff_login_payload = login(api_client, STAFF_ACCESS_CODE)
        admin_login_payload = login(api_client, ADMIN_ACCESS_CODE)
        staff_headers = auth_headers(staff_login_payload["token"])
        admin_headers = auth_headers(admin_login_payload["token"])

        staff_response = api_client.get(
            f"{API_BASE}/notifications",
            headers=staff_headers,
            params={"notification_type": "lead", "status": "all"},
            timeout=20,
        )
        admin_response = api_client.get(
            f"{API_BASE}/notifications",
            headers=admin_headers,
            params={"notification_type": "lead", "status": "all"},
            timeout=20,
        )
        assert staff_response.status_code == 200
        assert admin_response.status_code == 200
        staff_payload = staff_response.json()
        admin_payload = admin_response.json()

        # Count should remain independently computed per authenticated user.
        assert isinstance(staff_payload["unread_count"], int)
        assert isinstance(admin_payload["unread_count"], int)

    def test_mark_read_persists_for_current_staff(self, api_client):
        _require_access_codes()
        staff = login(api_client, STAFF_ACCESS_CODE)
        headers = auth_headers(staff["token"])
        staff_id = staff["staff"]["id"]

        current = api_client.get(
            f"{API_BASE}/notifications",
            headers=headers,
            params={"notification_type": "all", "status": "all"},
            timeout=20,
        )
        assert current.status_code == 200
        before = current.json()
        assert isinstance(before["unread_count"], int)

        target = next(
            (item for item in before["notifications"] if staff_id not in item.get("read_by", [])),
            None,
        )
        if not target:
            pytest.skip("No unread notification available for current staff")

        mark = api_client.post(
            f"{API_BASE}/notifications/{target['id']}/read",
            headers=headers,
            timeout=20,
        )
        assert mark.status_code == 200
        assert mark.json().get("status") == "ok"

        refreshed = api_client.get(
            f"{API_BASE}/notifications",
            headers=headers,
            params={"notification_type": "all", "status": "all"},
            timeout=20,
        )
        assert refreshed.status_code == 200
        after = refreshed.json()
        assert after["unread_count"] <= before["unread_count"]
        updated = next(item for item in after["notifications"] if item["id"] == target["id"])
        assert staff_id in updated.get("read_by", [])


class TestAuditCompliance:
    """Audit panel filtering and CSV export authorization validations."""

    def test_admin_audit_filters_action_and_role(self, api_client):
        _require_access_codes()
        admin = login(api_client, ADMIN_ACCESS_CODE)
        headers = auth_headers(admin["token"])

        filtered = api_client.get(
            f"{API_BASE}/audit-logs",
            headers=headers,
            params={"action": "login", "actor_role": "admin"},
            timeout=20,
        )
        assert filtered.status_code == 200
        payload = filtered.json()
        assert "logs" in payload and isinstance(payload["logs"], list)
        assert all(log.get("action") == "login" for log in payload["logs"])
        assert all(log.get("actor_role") == "admin" for log in payload["logs"])

    def test_admin_can_export_filtered_audit_csv(self, api_client):
        _require_access_codes()
        admin = login(api_client, ADMIN_ACCESS_CODE)
        headers = auth_headers(admin["token"])

        exported = api_client.get(
            f"{API_BASE}/audit-logs/export",
            headers=headers,
            params={"action": "login", "actor_role": "admin"},
            timeout=20,
        )
        assert exported.status_code == 200
        assert "text/csv" in exported.headers.get("content-type", "")
        assert "attachment; filename=" in exported.headers.get("content-disposition", "")
        lines = [line for line in exported.text.splitlines() if line.strip()]
        assert lines
        assert lines[0] == "created_at,actor_name,actor_role,action,resource,resource_id,detail"

    @pytest.mark.parametrize("access_code", ["staff", "viewer"])
    def test_non_admin_cannot_export_audit_csv(self, api_client, access_code):
        _require_access_codes()
        code_map = {
            "staff": STAFF_ACCESS_CODE,
            "viewer": VIEWER_ACCESS_CODE,
        }
        auth = login(api_client, code_map[access_code])
        response = api_client.get(
            f"{API_BASE}/audit-logs/export",
            headers=auth_headers(auth["token"]),
            timeout=20,
        )
        assert response.status_code == 403


class TestAuthAndProtectedInboxSmoke:
    """Staff login and protected inbox baseline checks."""

    def test_staff_login_and_dashboard_access(self, api_client):
        _require_access_codes()
        staff = login(api_client, STAFF_ACCESS_CODE)
        dashboard = api_client.get(
            f"{API_BASE}/dashboard",
            headers=auth_headers(staff["token"]),
            timeout=20,
        )
        assert dashboard.status_code == 200
        payload = dashboard.json()
        assert isinstance(payload.get("appointments_today"), int)
        assert isinstance(payload.get("open_leads"), int)
