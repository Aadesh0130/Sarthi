"""
Tests for the auth API (app/api/auth.py) added during the frontend+backend
integration -- wiring the uploaded project's own already-existing auth
backend (models/user.py, otp.py, trip.py, services/auth_service.py,
sms_service.py, core/security.py) to a real router. Everything below the
router itself (OTP hashing, rate limiting, JWT issuance) is that
pre-existing code, unmodified in behavior -- these tests exist to prove the
wiring (router -> service -> models -> one shared database) actually works,
not to re-test OTP cryptography from scratch.

The real 6-digit OTP is never returned in any API response (see
sms_service.py) so these tests monkeypatch the OTP generator to a known
value -- the same technique a developer would need in dev mode too, just
done here instead of reading it off server stdout.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_sarthi.db")

from fastapi.testclient import TestClient

from app.main import app
from app.services import auth_service as auth_service_module

client = TestClient(app)


def _fixed_otp(monkeypatch, value="123456"):
    monkeypatch.setattr(auth_service_module, "generate_secure_otp", lambda length=6: value)


def test_request_otp_never_returns_the_code(monkeypatch):
    _fixed_otp(monkeypatch, "555555")
    resp = client.post("/api/auth/phone/request-otp", json={"phone": "9812345601"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "555555" not in resp.text, "the OTP must never appear in the API response body"


def test_full_phone_login_flow_creates_real_user_and_issues_jwt(monkeypatch):
    _fixed_otp(monkeypatch, "111222")
    phone = "9812345602"

    otp_resp = client.post("/api/auth/phone/request-otp", json={"phone": phone})
    assert otp_resp.status_code == 200

    verify_resp = client.post("/api/auth/phone/verify-otp", json={"phone": phone, "otp": "111222"})
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert data["success"] is True
    assert data["token"]
    assert data["user"]["phone_number"] == "+91" + phone
    assert data["is_new_user"] is True

    # The issued JWT must actually authenticate a real protected endpoint,
    # against a real user row that was actually persisted.
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['token']}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["phone_number"] == "+91" + phone


def test_wrong_otp_is_rejected_and_reports_remaining_attempts(monkeypatch):
    _fixed_otp(monkeypatch, "999888")
    phone = "9812345603"
    client.post("/api/auth/phone/request-otp", json={"phone": phone})

    resp = client.post("/api/auth/phone/verify-otp", json={"phone": phone, "otp": "000000"})
    assert resp.status_code == 400
    assert "attempt" in resp.json()["detail"].lower()


def test_me_requires_authentication():
    # A fresh client, not the shared module-level one: verify-otp sets a real
    # sarthi_token cookie on success (defense-in-depth alongside the bearer
    # token), and TestClient persists cookies across calls on the same
    # instance -- exactly like a real browser would. This test is about an
    # unauthenticated visitor, so it needs a client that never received that
    # cookie in the first place.
    anon_client = TestClient(app)
    resp = anon_client.get("/api/auth/me")
    assert resp.status_code == 401


def test_invalid_phone_number_is_rejected():
    resp = client.post("/api/auth/phone/request-otp", json={"phone": "123"})
    assert resp.status_code == 400


def test_auth_status_reports_dev_mode_honestly():
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["phone_auth_available"] is True
    # No Twilio credentials are configured in this test environment.
    assert body["dev_mode"] is True
    assert body["sms_provider_configured"] is False
