"""Backend API tests for Complaint Intake app.

Covers:
- Health endpoint (GET /api/)
- Complaint extraction via text and file upload (POST /api/complaints/extract)
- Complaint save + list (POST /api/complaints/save, GET /api/complaints)
- Chat endpoint (POST /api/complaints/chat)
"""
from __future__ import annotations

import io
import os

import pytest
import requests

# Load frontend/.env for REACT_APP_BACKEND_URL (public URL through ingress)
FRONTEND_ENV = "/app/frontend/.env"
if os.path.exists(FRONTEND_ENV):
    with open(FRONTEND_ENV) as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                _, _, val = line.strip().partition("=")
                os.environ.setdefault("REACT_APP_BACKEND_URL", val.strip('"'))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
TIMEOUT = 60  # LLM calls can be slow

SAMPLE_TEXT = (
    "Dear QA, Acme Pharma reports batch B12345 of Amoxicillin 500mg "
    "(mfg 2024-01-15, exp 2026-01-14) had discoloration in 30 units. "
    "Received via email 2026-01-05. Contamination concern, high severity, "
    "urgent priority."
)


# -------------------- Fixtures -------------------- #


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    s = requests.Session()
    return s


# -------------------- Health -------------------- #


class TestHealth:
    def test_root_ok(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("service") == "complaint-intake"
        assert data.get("status") == "ok"


# -------------------- Extraction -------------------- #


class TestExtract:
    def test_extract_from_text(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/complaints/extract",
            data={"text": SAMPLE_TEXT},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "extracted" in body
        ex = body["extracted"]
        # Non-empty critical fields
        assert ex["batch_number"].strip() != ""
        assert "B12345" in ex["batch_number"]
        assert ex["customer_name"].strip() != ""
        assert ex["product_name"].strip() != ""
        assert ex["complaint_type"].strip() != ""
        assert ex["initial_severity"].strip() != ""
        assert ex["priority"].strip() != ""

    def test_extract_from_txt_file(self, api_client):
        content = SAMPLE_TEXT.encode("utf-8")
        files = {"file": ("complaint.txt", io.BytesIO(content), "text/plain")}
        r = api_client.post(
            f"{BASE_URL}/api/complaints/extract",
            files=files,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        ex = r.json()["extracted"]
        assert "B12345" in ex["batch_number"]
        assert ex["product_name"].strip() != ""

    def test_extract_no_input_returns_400(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/complaints/extract",
            data={},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400, r.text

    def test_extract_oversized_file_returns_413(self, api_client):
        # Generate 10MB + 1 byte of text data
        big = b"a" * (10 * 1024 * 1024 + 1)
        files = {"file": ("big.txt", io.BytesIO(big), "text/plain")}
        r = api_client.post(
            f"{BASE_URL}/api/complaints/extract",
            files=files,
            timeout=TIMEOUT,
        )
        assert r.status_code == 413, f"Expected 413, got {r.status_code}: {r.text[:200]}"


# -------------------- Save + List -------------------- #


class TestSaveAndList:
    def test_save_and_list_persists(self, api_client):
        payload = {
            "complaint_source": "Email",
            "customer_name": "TEST_Acme Pharma",
            "product_name": "Amoxicillin",
            "product_strength": "500 mg",
            "batch_number": "TEST_B12345",
            "manufacturing_date": "2024-01-15",
            "expiry_date": "2026-01-14",
            "quantity_affected": "30",
            "complaint_type": "Contamination",
            "complaint_date": "2026-01-05",
            "complaint_description": "Discoloration observed in 30 units.",
            "initial_severity": "High",
            "priority": "Urgent",
        }
        r = api_client.post(
            f"{BASE_URL}/api/complaints/save", json=payload, timeout=TIMEOUT
        )
        assert r.status_code == 200, r.text
        saved = r.json()
        assert "id" in saved
        assert isinstance(saved["id"], int)
        assert saved["status"] == "Pending Triage"
        assert saved["batch_number"] == "TEST_B12345"
        saved_id = saved["id"]

        # GET list and confirm the saved item is present
        r2 = api_client.get(f"{BASE_URL}/api/complaints", timeout=TIMEOUT)
        assert r2.status_code == 200, r2.text
        items = r2.json()
        assert isinstance(items, list)
        ids = [it["id"] for it in items]
        assert saved_id in ids, f"Saved complaint id {saved_id} not in list"

        found = next(it for it in items if it["id"] == saved_id)
        assert found["customer_name"] == "TEST_Acme Pharma"
        assert found["status"] == "Pending Triage"


# -------------------- Chat -------------------- #


class TestChat:
    def test_chat_returns_reply(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/complaints/chat",
            json={
                "message": "What is the batch number?",
                "form": {"batch_number": "B12345"},
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "reply" in body
        assert isinstance(body["reply"], str)
        assert len(body["reply"].strip()) > 0

    def test_chat_empty_message_returns_400(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/complaints/chat",
            json={"message": "   ", "form": {}},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400, r.text
