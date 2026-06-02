"""Notifications, chat-to-lead extraction, and audit log regression tests."""

import os
from datetime import datetime, timedelta, timezone

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
ADMIN_ACCESS_CODE = os.environ.get("STAFF_ADMIN_ACCESS_CODE", "FK-ADMIN-7X9Q2")
STAFF_ACCESS_CODE = os.environ.get("STAFF_STAFF_ACCESS_CODE", "FK-STAFF-4M8P1")


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def future_date(days_ahead: int = 14) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days_ahead)).isoformat()


def login_headers(api_client, access_code):
    response = api_client.post(
        f"{API_BASE}/auth/staff-login", json={"access_code": access_code}, timeout=20
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def get_first_slot(api_client, date):
    response = api_client.get(f"{API_BASE}/appointments/slots", params={"date": date}, timeout=20)
    assert response.status_code == 200
    available = [slot["time"] for slot in response.json()["slots"] if slot["available"]]
    assert available
    return available[0]


class TestNotificationsExtractionAudit:
    def test_appointment_creates_in_app_notification(self, api_client):
        headers = login_headers(api_client, STAFF_ACCESS_CODE)
        date = future_date()
        payload = {
            "name": "TEST Notify Appointment",
            "phone": "5559090000",
            "email": "notify.appointment@example.com",
            "service": "New client consultation",
            "date": date,
            "time": get_first_slot(api_client, date),
            "notes": "Notification regression test",
        }
        created = api_client.post(f"{API_BASE}/appointments", json=payload, timeout=20)
        assert created.status_code == 200

        notifications = api_client.get(f"{API_BASE}/notifications", headers=headers, timeout=20)
        assert notifications.status_code == 200
        titles = [item["title"] for item in notifications.json()["notifications"]]
        assert "New appointment booked" in titles

    def test_public_lead_creates_notification(self, api_client):
        staff_headers = login_headers(api_client, STAFF_ACCESS_CODE)
        admin_headers = login_headers(api_client, ADMIN_ACCESS_CODE)
        payload = {
            "name": "TEST Notify Lead",
            "phone": "5559091111",
            "email": "notify.lead@example.com",
            "interest": "Needs pricing callback",
            "preferred_contact_time": "Tomorrow morning",
        }
        lead = api_client.post(f"{API_BASE}/leads", json=payload, timeout=20)
        assert lead.status_code == 200

        staff_notifications = api_client.get(f"{API_BASE}/notifications", headers=staff_headers, timeout=20)
        admin_notifications = api_client.get(f"{API_BASE}/notifications", headers=admin_headers, timeout=20)
        assert staff_notifications.status_code == 200
        assert admin_notifications.status_code == 200
        assert any(item["title"] == "New callback request" for item in staff_notifications.json()["notifications"])
        assert any(item["title"] == "New callback request" for item in admin_notifications.json()["notifications"])

    def test_chat_to_lead_suggestion_and_approval(self, api_client):
        staff_headers = login_headers(api_client, STAFF_ACCESS_CODE)
        message = "My name is Riley Brooks and my phone is 555-909-2222. Please schedule a consultation callback."
        chat = api_client.post(f"{API_BASE}/chat/message", json={"message": message}, timeout=45)
        assert chat.status_code == 200

        leads = api_client.get(f"{API_BASE}/leads", headers=staff_headers, timeout=20)
        assert leads.status_code == 200
        suggested = next(
            item for item in leads.json()
            if item["source"] == "chat_extraction" and "Riley" in item["name"]
        )
        assert suggested["status"] == "suggested"

        approved = api_client.post(
            f"{API_BASE}/leads/{suggested['id']}/approve", headers=staff_headers, timeout=20
        )
        assert approved.status_code == 200
        assert approved.json()["lead"]["status"] == "new"

    def test_notifications_can_be_marked_read(self, api_client):
        headers = login_headers(api_client, STAFF_ACCESS_CODE)
        notifications = api_client.get(f"{API_BASE}/notifications", headers=headers, timeout=20)
        assert notifications.status_code == 200
        items = notifications.json()["notifications"]
        assert items

        mark = api_client.post(
            f"{API_BASE}/notifications/{items[0]['id']}/read", headers=headers, timeout=20
        )
        assert mark.status_code == 200

    def test_admin_can_view_audit_logs(self, api_client):
        headers = login_headers(api_client, ADMIN_ACCESS_CODE)
        response = api_client.get(f"{API_BASE}/audit-logs", headers=headers, timeout=20)
        assert response.status_code == 200
        logs = response.json()["logs"]
        assert isinstance(logs, list)
        assert any(log["action"] in ["login", "view", "lead_approved"] for log in logs)

    def test_notification_mark_read_reduces_unread_count(self, api_client):
        headers = login_headers(api_client, STAFF_ACCESS_CODE)
        first = api_client.get(f"{API_BASE}/notifications", headers=headers, timeout=20)
        assert first.status_code == 200
        first_payload = first.json()
        assert isinstance(first_payload["unread_count"], int)

        target = next(
            (item for item in first_payload["notifications"] if "staff-frontkind" not in item.get("read_by", [])),
            None,
        )
        if not target:
            pytest.skip("No unread notification available for staff test user")

        mark = api_client.post(
            f"{API_BASE}/notifications/{target['id']}/read", headers=headers, timeout=20
        )
        assert mark.status_code == 200

        second = api_client.get(f"{API_BASE}/notifications", headers=headers, timeout=20)
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["unread_count"] <= first_payload["unread_count"]
        marked_item = next(item for item in second_payload["notifications"] if item["id"] == target["id"])
        assert "staff-frontkind" in marked_item.get("read_by", [])

    def test_audit_logs_capture_required_activity_categories(self, api_client):
        admin_headers = login_headers(api_client, ADMIN_ACCESS_CODE)

        dashboard = api_client.get(f"{API_BASE}/dashboard", headers=admin_headers, timeout=20)
        leads = api_client.get(f"{API_BASE}/leads", headers=admin_headers, timeout=20)
        appointments = api_client.get(f"{API_BASE}/appointments", headers=admin_headers, timeout=20)
        notifications = api_client.get(f"{API_BASE}/notifications", headers=admin_headers, timeout=20)
        sessions = api_client.get(f"{API_BASE}/chat/sessions", headers=admin_headers, timeout=20)
        assert dashboard.status_code == 200
        assert leads.status_code == 200
        assert appointments.status_code == 200
        assert notifications.status_code == 200
        assert sessions.status_code == 200

        sessions_list = sessions.json()
        if sessions_list:
            messages = api_client.get(
                f"{API_BASE}/chat/messages/{sessions_list[0]['id']}", headers=admin_headers, timeout=20
            )
            assert messages.status_code == 200

        profile = api_client.get(f"{API_BASE}/business-profile", timeout=20)
        assert profile.status_code == 200
        original_hours = profile.json()["hours"]
        temp_hours = "Monday to Friday, 8:45 AM – 5:45 PM"
        patch = api_client.patch(
            f"{API_BASE}/business-profile",
            headers=admin_headers,
            json={"hours": temp_hours},
            timeout=20,
        )
        assert patch.status_code == 200
        restore = api_client.patch(
            f"{API_BASE}/business-profile",
            headers=admin_headers,
            json={"hours": original_hours},
            timeout=20,
        )
        assert restore.status_code == 200

        logout = api_client.post(f"{API_BASE}/auth/logout", headers=admin_headers, timeout=20)
        assert logout.status_code == 200

        relog_headers = login_headers(api_client, ADMIN_ACCESS_CODE)
        logs_response = api_client.get(f"{API_BASE}/audit-logs", headers=relog_headers, timeout=20)
        assert logs_response.status_code == 200
        logs = logs_response.json()["logs"]

        actions = {entry["action"] for entry in logs}
        resources = {entry["resource"] for entry in logs}

        assert "login" in actions
        assert "view" in actions
        assert "profile_update" in actions
        assert "logout" in actions
        assert "dashboard" in resources
        assert "leads" in resources
        assert "appointments" in resources
        assert "notifications" in resources
        assert "chat_messages" in resources or "chat_sessions" in resources
