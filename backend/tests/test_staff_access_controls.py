"""Staff auth and role-protection regression tests for receptionist APIs."""

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


BASE_URL = _get_base_url()
API_BASE = f"{BASE_URL}/api"
ADMIN_ACCESS_CODE = os.environ.get("STAFF_ADMIN_ACCESS_CODE", "FK-ADMIN-7X9Q2")
STAFF_ACCESS_CODE = os.environ.get("STAFF_STAFF_ACCESS_CODE", "FK-STAFF-4M8P1")
VIEWER_ACCESS_CODE = os.environ.get("STAFF_VIEWER_ACCESS_CODE", "FK-VIEW-6L3N5")


def future_date(days_ahead: int = 10) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days_ahead)).isoformat()


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def staff_login(api_client, access_code):
    response = api_client.post(
        f"{API_BASE}/auth/staff-login", json={"access_code": access_code}, timeout=20
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("token"), str) and payload["token"].strip()
    assert isinstance(payload.get("staff"), dict)
    return payload


def auth_header(api_client, access_code):
    token = staff_login(api_client, access_code)["token"]
    return {"Authorization": f"Bearer {token}"}


class TestStaffProtectedRoutes:
    """Verify Bearer token gate for protected dashboard/inbox routes."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/dashboard",
            "/leads",
            "/appointments",
            "/chat/sessions",
        ],
    )
    def test_protected_routes_reject_missing_token(self, api_client, endpoint):
        response = api_client.get(f"{API_BASE}{endpoint}", timeout=20)
        assert response.status_code == 401
        detail = response.json().get("detail", "")
        assert "staff" in detail.lower() or "login" in detail.lower()

    def test_chat_messages_route_rejects_missing_token(self, api_client):
        create = api_client.post(
            f"{API_BASE}/chat/message",
            json={"session_id": None, "message": "Hello from protected-route test"},
            timeout=30,
        )
        assert create.status_code == 200
        session_id = create.json()["session_id"]

        response = api_client.get(f"{API_BASE}/chat/messages/{session_id}", timeout=20)
        assert response.status_code == 401
        assert "detail" in response.json()


class TestRoleProtection:
    """Validate viewer/staff/admin role capabilities and restrictions."""

    def test_viewer_can_access_dashboard_but_not_leads(self, api_client):
        headers = auth_header(api_client, VIEWER_ACCESS_CODE)
        dashboard = api_client.get(f"{API_BASE}/dashboard", headers=headers, timeout=20)
        leads = api_client.get(f"{API_BASE}/leads", headers=headers, timeout=20)

        assert dashboard.status_code == 200
        dashboard_data = dashboard.json()
        assert isinstance(dashboard_data["appointments_today"], int)
        assert isinstance(dashboard_data["open_leads"], int)
        assert leads.status_code == 403

    def test_staff_can_access_leads_but_not_edit_business_profile(self, api_client):
        headers = auth_header(api_client, STAFF_ACCESS_CODE)
        leads = api_client.get(f"{API_BASE}/leads", headers=headers, timeout=20)
        patch = api_client.patch(
            f"{API_BASE}/business-profile",
            headers=headers,
            json={"hours": "Monday to Friday, 8:00 AM – 5:00 PM"},
            timeout=20,
        )

        assert leads.status_code == 200
        assert isinstance(leads.json(), list)
        assert patch.status_code == 403

    def test_admin_can_edit_business_profile(self, api_client):
        get_profile = api_client.get(f"{API_BASE}/business-profile", timeout=20)
        assert get_profile.status_code == 200
        original = get_profile.json()

        headers = auth_header(api_client, ADMIN_ACCESS_CODE)
        next_hours = "Monday to Friday, 8:30 AM – 5:30 PM"
        patch = api_client.patch(
            f"{API_BASE}/business-profile",
            headers=headers,
            json={"hours": next_hours},
            timeout=20,
        )
        assert patch.status_code == 200
        assert patch.json()["hours"] == next_hours

        verify = api_client.get(f"{API_BASE}/business-profile", timeout=20)
        assert verify.status_code == 200
        assert verify.json()["hours"] == next_hours

        restore = api_client.patch(
            f"{API_BASE}/business-profile",
            headers=headers,
            json={"hours": original["hours"]},
            timeout=20,
        )
        assert restore.status_code == 200
        assert restore.json()["hours"] == original["hours"]


class TestPublicFlowsWithoutStaffToken:
    """Ensure visitor-facing APIs continue to work without staff auth token."""

    def test_public_business_profile_and_chat_message(self, api_client):
        profile = api_client.get(f"{API_BASE}/business-profile", timeout=20)
        assert profile.status_code == 200
        assert profile.json()["id"] == "default-profile"

        chat = api_client.post(
            f"{API_BASE}/chat/message",
            json={"session_id": None, "message": "What are your office hours?"},
            timeout=45,
        )
        assert chat.status_code == 200
        chat_data = chat.json()
        assert isinstance(chat_data["session_id"], str) and chat_data["session_id"].strip()
        assert isinstance(chat_data["message"], str) and chat_data["message"].strip()
        assert chat_data.get("mode") in ["live", "mocked"]

    def test_public_appointment_and_lead_creation(self, api_client):
        date = future_date()
        slots = api_client.get(f"{API_BASE}/appointments/slots", params={"date": date}, timeout=20)
        assert slots.status_code == 200
        slot_payload = slots.json()
        assert slot_payload["date"] == date
        available = [slot["time"] for slot in slot_payload["slots"] if slot["available"]]
        assert available

        appointment_payload = {
            "name": "TEST_Public Flow Booking",
            "phone": "5550303000",
            "email": "test.public.booking@example.com",
            "service": "New client consultation",
            "date": date,
            "time": available[0],
            "notes": "Public booking test",
        }
        book = api_client.post(f"{API_BASE}/appointments", json=appointment_payload, timeout=20)
        assert book.status_code == 200
        booked = book.json()
        assert booked["name"] == appointment_payload["name"]
        assert booked["time"] == appointment_payload["time"]

        leads_payload = {
            "name": "TEST_Public Flow Lead",
            "phone": "5550404000",
            "email": "test.public.lead@example.com",
            "interest": "Need callback for service details",
            "preferred_contact_time": "Tomorrow afternoon",
            "source": "receptionist",
        }
        lead = api_client.post(f"{API_BASE}/leads", json=leads_payload, timeout=20)
        assert lead.status_code == 200
        created_lead = lead.json()
        assert created_lead["name"] == leads_payload["name"]
        assert created_lead["interest"] == leads_payload["interest"]