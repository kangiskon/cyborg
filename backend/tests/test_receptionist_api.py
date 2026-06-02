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
        response = api_client.get(f"{API_BASE}/dashboard", timeout=20)
        assert response.status_code == 200
        data = response.json()
        assert "appointments_today" in data and isinstance(data["appointments_today"], int)
        assert "open_leads" in data and isinstance(data["open_leads"], int)
        assert "total_conversations" in data and isinstance(data["total_conversations"], int)
        assert "next_appointments" in data and isinstance(data["next_appointments"], list)
        assert "recent_leads" in data and isinstance(data["recent_leads"], list)
        assert "_id" not in str(data)

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

    def test_appointment_slots_booking_and_unavailability(self, api_client):
        test_date = (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat()

        slots_before_resp = api_client.get(
            f"{API_BASE}/appointments/slots", params={"date": test_date}, timeout=20
        )
        assert slots_before_resp.status_code == 200
        slots_before = slots_before_resp.json()["slots"]
        available_before = [slot["time"] for slot in slots_before if slot["available"]]
        assert len(available_before) > 0
        chosen_time = available_before[0]

        booking_payload = {
            "name": "TEST_Agent Booking",
            "phone": "5550101000",
            "email": "test.booking@example.com",
            "service": "New client consultation",
            "date": test_date,
            "time": chosen_time,
            "notes": "Created by automated API test",
        }
        booking_resp = api_client.post(
            f"{API_BASE}/appointments", json=booking_payload, timeout=20
        )
        assert booking_resp.status_code == 200
        booking_data = booking_resp.json()
        assert booking_data["name"] == booking_payload["name"]
        assert booking_data["date"] == test_date
        assert booking_data["time"] == chosen_time
        assert isinstance(booking_data["id"], str) and booking_data["id"].strip()

        slots_after_resp = api_client.get(
            f"{API_BASE}/appointments/slots", params={"date": test_date}, timeout=20
        )
        assert slots_after_resp.status_code == 200
        slots_after = slots_after_resp.json()["slots"]
        chosen_slot = next(slot for slot in slots_after if slot["time"] == chosen_time)
        assert chosen_slot["available"] is False

    def test_lead_capture_and_dashboard_updates(self, api_client):
        before_dashboard_resp = api_client.get(f"{API_BASE}/dashboard", timeout=20)
        assert before_dashboard_resp.status_code == 200
        before_dashboard = before_dashboard_resp.json()
        before_open_leads = before_dashboard["open_leads"]

        lead_payload = {
            "name": "TEST_Agent Lead",
            "phone": "5550202000",
            "email": "test.lead@example.com",
            "interest": "Need callback for consultation",
            "preferred_contact_time": "Tomorrow afternoon",
            "source": "receptionist",
        }
        create_resp = api_client.post(f"{API_BASE}/leads", json=lead_payload, timeout=20)
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert created["name"] == lead_payload["name"]
        assert created["phone"] == lead_payload["phone"]
        assert created["interest"] == lead_payload["interest"]
        assert created["status"] == "new"

        leads_resp = api_client.get(f"{API_BASE}/leads", timeout=20)
        assert leads_resp.status_code == 200
        leads = leads_resp.json()
        assert any(item["id"] == created["id"] for item in leads)

        after_dashboard_resp = api_client.get(f"{API_BASE}/dashboard", timeout=20)
        assert after_dashboard_resp.status_code == 200
        after_dashboard = after_dashboard_resp.json()
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
            f"{API_BASE}/business-profile", json=update_payload, timeout=20
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
            f"{API_BASE}/business-profile", json=restore_payload, timeout=20
        )
        assert restore_resp.status_code == 200
