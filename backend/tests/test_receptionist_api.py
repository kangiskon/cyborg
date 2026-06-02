"""Critical API regression tests for AI receptionist core flows."""

import os
from datetime import datetime, timedelta, timezone

import pytest
import requests


def _get_base_url() -> str:
    """Read preview URL from environment first, then frontend/.env."""
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
ADMIN_ACCESS_CODE = "FK-ADMIN-7X9Q2"
STAFF_ACCESS_CODE = "FK-STAFF-4M8P1"
VIEWER_ACCESS_CODE = "FK-VIEW-6L3N5"


def future_date(days_ahead: int = 2) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days_ahead)).isoformat()


def assert_dashboard_shape(data):
    assert "appointments_today" in data and isinstance(data["appointments_today"], int)
    assert "open_leads" in data and isinstance(data["open_leads"], int)
    assert "total_conversations" in data and isinstance(data["total_conversations"], int)
    assert "next_appointments" in data and isinstance(data["next_appointments"], list)
    assert "recent_leads" in data and isinstance(data["recent_leads"], list)
    assert "_id" not in str(data)


def get_dashboard(api_client):
    response = api_client.get(
        f"{API_BASE}/dashboard", headers=auth_header(api_client, VIEWER_ACCESS_CODE), timeout=20
    )
    assert response.status_code == 200
    return response.json()


def get_slots(api_client, date):
    response = api_client.get(
        f"{API_BASE}/appointments/slots", params={"date": date}, timeout=20
    )
    assert response.status_code == 200
    return response.json()["slots"]


def first_available_time(slots):
    available_times = [slot["time"] for slot in slots if slot["available"]]
    assert available_times
    return available_times[0]


def create_booking(api_client, date, time):
    payload = {
        "name": "TEST_Agent Booking",
        "phone": "5550101000",
        "email": "test.booking@example.com",
        "service": "New client consultation",
        "date": date,
        "time": time,
        "notes": "Created by automated API test",
    }
    response = api_client.post(f"{API_BASE}/appointments", json=payload, timeout=20)
    assert response.status_code == 200
    return payload, response.json()


def create_lead(api_client):
    payload = {
        "name": "TEST_Agent Lead",
        "phone": "5550202000",
        "email": "test.lead@example.com",
        "interest": "Need callback for consultation",
        "preferred_contact_time": "Tomorrow afternoon",
        "source": "receptionist",
    }
    response = api_client.post(f"{API_BASE}/leads", json=payload, timeout=20)
    assert response.status_code == 200
    return payload, response.json()


def staff_login(api_client, access_code):
    response = api_client.post(
        f"{API_BASE}/auth/staff-login", json={"access_code": access_code}, timeout=20
    )
    assert response.status_code == 200
    return response.json()


def auth_header(api_client, access_code):
    token = staff_login(api_client, access_code)["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestReceptionistApi:
    """Business profile, dashboard, chat, booking, and lead flows."""

    def test_business_profile_default_shape(self, api_client):
        response = api_client.get(f"{API_BASE}/business-profile", timeout=20)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "default-profile"
        assert isinstance(data["business_name"], str) and data["business_name"].strip()
        assert isinstance(data["hours"], str) and data["hours"].strip()
        assert isinstance(data["business_types"], list) and len(data["business_types"]) > 0

    def test_dashboard_response_and_no_objectid_serialization(self, api_client):
        assert_dashboard_shape(get_dashboard(api_client))

    def test_chat_message_returns_graceful_response(self, api_client):
        payload = {
            "message": "Do you have openings today?",
            "session_id": None,
        }
        response = api_client.post(f"{API_BASE}/chat/message", json=payload, timeout=45)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data.get("session_id"), str) and data["session_id"].strip()
        assert isinstance(data.get("message"), str) and data["message"].strip()
        assert data.get("mode") in ["live", "mocked"]

    def test_dashboard_requires_staff_login(self, api_client):
        response = api_client.get(f"{API_BASE}/dashboard", timeout=20)
        assert response.status_code == 401

    def test_staff_login_returns_role_token(self, api_client):
        data = staff_login(api_client, ADMIN_ACCESS_CODE)
        assert data["token"]
        assert data["staff"]["email"] == "admin@frontkind.app"
        assert data["staff"]["role"] == "admin"

    def test_viewer_can_access_dashboard_not_leads(self, api_client):
        headers = auth_header(api_client, VIEWER_ACCESS_CODE)
        dashboard_response = api_client.get(f"{API_BASE}/dashboard", headers=headers, timeout=20)
        leads_response = api_client.get(f"{API_BASE}/leads", headers=headers, timeout=20)
        assert dashboard_response.status_code == 200
        assert leads_response.status_code == 403

    def test_staff_can_access_leads_not_profile_edit(self, api_client):
        headers = auth_header(api_client, STAFF_ACCESS_CODE)
        leads_response = api_client.get(f"{API_BASE}/leads", headers=headers, timeout=20)
        patch_response = api_client.patch(
            f"{API_BASE}/business-profile",
            headers=headers,
            json={"hours": "Monday to Friday, 9:00 AM – 6:00 PM"},
            timeout=20,
        )
        assert leads_response.status_code == 200
        assert patch_response.status_code == 403

    def test_appointment_slots_have_availability(self, api_client):
        slots = get_slots(api_client, future_date())
        assert first_available_time(slots)

    def test_booking_marks_slot_unavailable(self, api_client):
        test_date = future_date(days_ahead=3)
        chosen_time = first_available_time(get_slots(api_client, test_date))
        booking_payload, booking_data = create_booking(api_client, test_date, chosen_time)

        assert booking_data["name"] == booking_payload["name"]
        assert booking_data["date"] == test_date
        assert booking_data["time"] == chosen_time
        assert isinstance(booking_data["id"], str) and booking_data["id"].strip()

        slots_after = get_slots(api_client, test_date)
        chosen_slot = next(slot for slot in slots_after if slot["time"] == chosen_time)
        assert not chosen_slot["available"]

    def test_lead_capture_appears_in_list(self, api_client):
        lead_payload, created = create_lead(api_client)
        assert created["name"] == lead_payload["name"]
        assert created["phone"] == lead_payload["phone"]
        assert created["interest"] == lead_payload["interest"]
        assert created["status"] == "new"

        leads_resp = api_client.get(
            f"{API_BASE}/leads", headers=auth_header(api_client, STAFF_ACCESS_CODE), timeout=20
        )
        assert leads_resp.status_code == 200
        assert any(item["id"] == created["id"] for item in leads_resp.json())

    def test_lead_capture_updates_dashboard(self, api_client):
        before_dashboard = get_dashboard(api_client)
        before_open_leads = before_dashboard["open_leads"]
        _, created = create_lead(api_client)
        after_dashboard = get_dashboard(api_client)

        assert after_dashboard["open_leads"] >= before_open_leads
        assert any(item["id"] == created["id"] for item in after_dashboard["recent_leads"])

    def test_business_profile_update_persists_business_name_and_hours(self, api_client):
        get_resp = api_client.get(f"{API_BASE}/business-profile", timeout=20)
        assert get_resp.status_code == 200
        original = get_resp.json()

        updated_name = f"{original['business_name']} TEST"
        updated_hours = "Monday to Friday, 8:00 AM – 6:00 PM"

        update_payload = {
            "business_name": updated_name,
            "business_types": original["business_types"],
            "voice": original["voice"],
            "hours": updated_hours,
            "location": original["location"],
            "services": original["services"],
            "faq": original["faq"],
        }
        put_resp = api_client.put(
            f"{API_BASE}/business-profile",
            headers=auth_header(api_client, ADMIN_ACCESS_CODE),
            json=update_payload,
            timeout=20,
        )
        assert put_resp.status_code == 200
        put_data = put_resp.json()
        assert put_data["business_name"] == updated_name
        assert put_data["hours"] == updated_hours

        verify_resp = api_client.get(f"{API_BASE}/business-profile", timeout=20)
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        assert verify_data["business_name"] == updated_name
        assert verify_data["hours"] == updated_hours

        restore_payload = {
            "business_name": original["business_name"],
            "business_types": original["business_types"],
            "voice": original["voice"],
            "hours": original["hours"],
            "location": original["location"],
            "services": original["services"],
            "faq": original["faq"],
        }
        restore_resp = api_client.put(
            f"{API_BASE}/business-profile",
            headers=auth_header(api_client, ADMIN_ACCESS_CODE),
            json=restore_payload,
            timeout=20,
        )
        assert restore_resp.status_code == 200
