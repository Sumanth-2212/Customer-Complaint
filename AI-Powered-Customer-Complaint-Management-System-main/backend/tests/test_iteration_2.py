"""Iteration 2 backend tests for the Complaint Intake app.

Covers new features:
  1) GET /api/complaints?limit=10 (history)
  2) POST /api/complaints/extract/stream (SSE streaming extraction)
  3) GET /api/complaints/{id}/pdf (ReportLab PDF export)
  4) GET /api/complaints/duplicate-check?batch=X (duplicate detector)
Plus regression on: /api/, /api/complaints/extract (text), /api/complaints/save,
/api/complaints/chat (valid + empty).
"""
from __future__ import annotations

import io
import json
import os
import time

import pytest
import requests

# Load frontend/.env for REACT_APP_BACKEND_URL
FRONTEND_ENV = "/app/frontend/.env"
if os.path.exists(FRONTEND_ENV):
    with open(FRONTEND_ENV) as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                _, _, val = line.strip().partition("=")
                os.environ.setdefault("REACT_APP_BACKEND_URL", val.strip('"'))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
TIMEOUT = 60  # LLM calls can be slow
STREAM_TIMEOUT = 30

STREAM_TEXT = (
    "Acme Global reports batch STREAM99 of Metformin 850mg contamination, "
    "5 units, email 2026-02-10, high severity, urgent priority."
)


# -------------------- Fixtures -------------------- #


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    return requests.Session()


@pytest.fixture(scope="module")
def seed_complaint(api_client) -> dict:
    """Ensure a TEST_B12345 complaint exists for duplicate-check + provide fresh id."""
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
    r = api_client.post(f"{BASE_URL}/api/complaints/save", json=payload, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()


# -------------------- 1) History: GET /api/complaints?limit=10 -------------------- #


class TestHistory:
    def test_list_limit_10_newest_first(self, api_client, seed_complaint):
        r = api_client.get(f"{BASE_URL}/api/complaints?limit=10", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list)
        assert len(items) <= 10
        assert len(items) >= 1
        # Each item is a dict containing at least id/created_at/batch_number/status
        for it in items:
            assert isinstance(it, dict)
            assert "id" in it and isinstance(it["id"], int)
            assert "created_at" in it
            assert "batch_number" in it
            assert "status" in it
        # newest first — created_at values should be non-increasing
        created = [it["created_at"] for it in items if it.get("created_at")]
        assert created == sorted(created, reverse=True), "results not newest-first"


# -------------------- 2) SSE: POST /api/complaints/extract/stream -------------------- #


def _parse_sse(body_text: str) -> list[dict]:
    """Parse an SSE payload into a list of decoded JSON events."""
    events: list[dict] = []
    for frame in body_text.split("\n\n"):
        frame = frame.strip()
        if not frame:
            continue
        for line in frame.splitlines():
            if line.startswith("data:"):
                data = line[len("data:"):].strip()
                if not data:
                    continue
                try:
                    events.append(json.loads(data))
                except json.JSONDecodeError:
                    pass
    return events


class TestStreamExtract:
    def test_stream_emits_start_fields_done(self, api_client):
        deadline = time.time() + STREAM_TIMEOUT
        with api_client.post(
            f"{BASE_URL}/api/complaints/extract/stream",
            data={"text": STREAM_TEXT},
            stream=True,
            timeout=STREAM_TIMEOUT,
        ) as r:
            assert r.status_code == 200, r.text
            ctype = r.headers.get("Content-Type", "")
            assert "text/event-stream" in ctype, f"unexpected content-type: {ctype}"

            # Collect the raw body chunk by chunk with an overall deadline.
            chunks = []
            for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    chunks.append(chunk)
                if time.time() > deadline:
                    break
            body = "".join(chunks)

        events = _parse_sse(body)
        assert events, f"No SSE events parsed. Raw body head: {body[:400]!r}"

        types = [e.get("type") for e in events]
        assert "start" in types, f"missing 'start' event, got types={types}"
        assert "done" in types, f"missing 'done' event, got types={types}"

        # Collect field events
        fields = {e["key"]: e.get("value", "") for e in events if e.get("type") == "field"}
        required_keys = {
            "customer_name",
            "product_name",
            "batch_number",
            "complaint_type",
            "initial_severity",
            "priority",
        }
        missing = required_keys - set(fields.keys())
        assert not missing, f"missing field events: {missing}. Got fields: {list(fields.keys())}"

        # Sanity: at least one non-empty extracted value
        non_empty = [k for k, v in fields.items() if str(v).strip()]
        assert non_empty, f"all field values empty; fields={fields}"

    def test_stream_empty_body_returns_400(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/complaints/extract/stream",
            data={},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400, r.text

    def test_stream_unsupported_extension_returns_415(self, api_client):
        files = {"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")}
        r = api_client.post(
            f"{BASE_URL}/api/complaints/extract/stream",
            files=files,
            timeout=TIMEOUT,
        )
        assert r.status_code == 415, f"expected 415 got {r.status_code}: {r.text[:200]}"


# -------------------- 3) Duplicate detector -------------------- #


class TestDuplicateCheck:
    def test_duplicate_match_case_insensitive(self, api_client, seed_complaint):
        # Query with mixed-case to verify case-insensitive match
        r = api_client.get(
            f"{BASE_URL}/api/complaints/duplicate-check",
            params={"batch": "test_b12345"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "count" in body and "matches" in body
        assert body["count"] >= 1
        assert isinstance(body["matches"], list) and len(body["matches"]) >= 1
        first = body["matches"][0]
        assert "id" in first and isinstance(first["id"], int)
        assert first.get("batch_number", "").lower() == "test_b12345"

    def test_duplicate_nonexistent_batch(self, api_client):
        r = api_client.get(
            f"{BASE_URL}/api/complaints/duplicate-check",
            params={"batch": "NONEXISTENT_BATCH_XYZ"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"count": 0, "matches": []}

    def test_duplicate_empty_batch_no_500(self, api_client):
        r = api_client.get(
            f"{BASE_URL}/api/complaints/duplicate-check",
            params={"batch": ""},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"count": 0, "matches": []}


# -------------------- 4) PDF export + GET by id -------------------- #


class TestPdfAndGetById:
    def test_get_complaint_by_id_200_and_404(self, api_client, seed_complaint):
        cid = seed_complaint["id"]
        r = api_client.get(f"{BASE_URL}/api/complaints/{cid}", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["id"] == cid
        assert got["batch_number"] == "TEST_B12345"

        # 404 for a very large non-existent id
        r404 = api_client.get(f"{BASE_URL}/api/complaints/9999999", timeout=TIMEOUT)
        assert r404.status_code == 404

    def test_pdf_download_after_fresh_save(self, api_client):
        # Fresh save
        payload = {
            "complaint_source": "Email",
            "customer_name": "TEST_PDF Corp",
            "product_name": "Paracetamol",
            "product_strength": "500 mg",
            "batch_number": "TEST_PDFB1",
            "manufacturing_date": "2024-06-01",
            "expiry_date": "2026-06-01",
            "quantity_affected": "10",
            "complaint_type": "Packaging",
            "complaint_date": "2026-02-01",
            "complaint_description": "Broken seal on outer carton.",
            "initial_severity": "Medium",
            "priority": "High",
        }
        s = api_client.post(f"{BASE_URL}/api/complaints/save", json=payload, timeout=TIMEOUT)
        assert s.status_code == 200, s.text
        cid = s.json()["id"]

        r = api_client.get(f"{BASE_URL}/api/complaints/{cid}/pdf", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        assert r.headers.get("Content-Type", "").startswith("application/pdf")
        assert r.content[:5] == b"%PDF-", f"body does not start with %PDF-: {r.content[:20]!r}"
        assert len(r.content) > 1000, f"PDF too small: {len(r.content)} bytes"

    def test_pdf_not_found_returns_404(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/complaints/9999999/pdf", timeout=TIMEOUT)
        assert r.status_code == 404


# -------------------- Regression -------------------- #


class TestRegression:
    def test_root(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/", timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json().get("service") == "complaint-intake"

    def test_extract_non_stream_text(self, api_client):
        text = (
            "Dear QA, Acme Pharma reports batch B12345 of Amoxicillin 500mg "
            "had discoloration in 30 units. Contamination, high severity, urgent priority."
        )
        r = api_client.post(
            f"{BASE_URL}/api/complaints/extract",
            data={"text": text},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        ex = r.json()["extracted"]
        assert "B12345" in ex["batch_number"]
        assert ex["product_name"].strip()

    def test_save_persists(self, api_client):
        payload = {
            "complaint_source": "Portal",
            "customer_name": "TEST_Reg Save",
            "product_name": "Ibuprofen",
            "batch_number": "TEST_REG1",
            "complaint_type": "Efficacy",
            "initial_severity": "Low",
            "priority": "Low",
        }
        r = api_client.post(f"{BASE_URL}/api/complaints/save", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "Pending Triage"
        assert body["batch_number"] == "TEST_REG1"

    def test_chat_valid(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/complaints/chat",
            json={"message": "Summarise the complaint", "form": {"batch_number": "B12345"}},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("reply", "").strip()

    def test_chat_empty_returns_400(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/complaints/chat",
            json={"message": "  ", "form": {}},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400
