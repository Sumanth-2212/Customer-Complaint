"""Iteration 3 backend tests for the Complaint Intake app.

Covers the three new features:
  1) GET /api/complaints/severity-summary?days=N (heatmap)
  2) POST/GET/GET-file/DELETE /api/complaints/{id}/evidence[/{eid}[/file]]
  3) POST /api/recalls  +  GET /api/recalls
Also verifies GET /api/complaints/duplicate-check now returns total_quantity_affected
and that the PDF becomes larger after image evidence is attached (inline images).
"""
from __future__ import annotations

import io
import os
import struct
import zlib

import pytest
import requests


# --- Load REACT_APP_BACKEND_URL from /app/frontend/.env ---
FRONTEND_ENV = "/app/frontend/.env"
if os.path.exists(FRONTEND_ENV):
    with open(FRONTEND_ENV) as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                _, _, val = line.strip().partition("=")
                os.environ.setdefault("REACT_APP_BACKEND_URL", val.strip('"'))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
TIMEOUT = 60


# ------------------------- helpers ------------------------- #


def _tiny_png_bytes(width: int = 8, height: int = 8) -> bytes:
    """Return a valid tiny PNG (RGBA) as raw bytes."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    row = b"\x00" + b"\xff\x00\x00\xff" * width  # red pixels
    raw = row * height
    idat = zlib.compress(raw, 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _large_png_bytes() -> bytes:
    """Return >10MB payload framed as a .png upload for size-limit tests."""
    # 11 MB of random-ish bytes prefixed with PNG signature so server picks up ext
    return b"\x89PNG\r\n\x1a\n" + (b"A" * (11 * 1024 * 1024))


# ------------------------- fixtures ------------------------- #


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    return requests.Session()


@pytest.fixture(scope="module")
def evidence_complaint(api_client) -> dict:
    """Create a fresh EV_BATCH_TEST complaint used by evidence & pdf tests."""
    payload = {
        "complaint_source": "Email",
        "customer_name": "TEST_Evidence Co",
        "product_name": "Amoxicillin",
        "product_strength": "500 mg",
        "batch_number": "EV_BATCH_TEST",
        "manufacturing_date": "2024-05-10",
        "expiry_date": "2026-05-10",
        "quantity_affected": "50",
        "complaint_type": "Contamination",
        "complaint_date": "2026-01-10",
        "complaint_description": "Discoloration observed.",
        "initial_severity": "High",
        "priority": "Urgent",
    }
    r = api_client.post(f"{BASE_URL}/api/complaints/save", json=payload, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def dup_seed_complaint(api_client) -> dict:
    """Ensure the TEST_B12345 batch has at least one complaint with a numeric quantity."""
    payload = {
        "complaint_source": "Email",
        "customer_name": "TEST_QtyCheck",
        "product_name": "Amoxicillin",
        "batch_number": "TEST_B12345",
        "quantity_affected": "30",
        "complaint_type": "Contamination",
        "initial_severity": "High",
        "priority": "Urgent",
    }
    r = api_client.post(f"{BASE_URL}/api/complaints/save", json=payload, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()


# ================= 1) Severity summary ================= #


class TestSeveritySummary:
    def test_default_days_30_shape(self, api_client):
        r = api_client.get(
            f"{BASE_URL}/api/complaints/severity-summary",
            params={"days": 30},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("days") == 30
        series = body.get("series")
        totals = body.get("totals")
        assert isinstance(series, list) and len(series) == 30, f"expected 30 entries, got {len(series) if isinstance(series, list) else series}"
        for entry in series:
            assert "date" in entry
            for k in ("Low", "Medium", "High", "Critical", "Unset"):
                assert k in entry, f"missing '{k}' in entry {entry}"
                assert isinstance(entry[k], int), f"'{k}' not int in {entry}"
        assert isinstance(totals, dict)
        for k in ("Low", "Medium", "High", "Critical", "Unset"):
            assert k in totals and isinstance(totals[k], int)

    def test_days_1_returns_single_entry(self, api_client):
        r = api_client.get(
            f"{BASE_URL}/api/complaints/severity-summary",
            params={"days": 1},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["days"] == 1
        assert isinstance(body["series"], list) and len(body["series"]) == 1

    def test_route_not_shadowed_by_id_route(self, api_client):
        # Confirm literal path is not interpreted as complaint_id lookup
        r = api_client.get(
            f"{BASE_URL}/api/complaints/severity-summary?days=7",
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert "series" in r.json()


# ================= 2) Duplicate-check total_quantity_affected ================= #


class TestDuplicateCheckTotals:
    def test_total_quantity_affected_present(self, api_client, dup_seed_complaint):
        r = api_client.get(
            f"{BASE_URL}/api/complaints/duplicate-check",
            params={"batch": "TEST_B12345"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "count" in body and "matches" in body
        assert "total_quantity_affected" in body, f"missing total_quantity_affected: {body}"
        assert isinstance(body["total_quantity_affected"], int)
        assert body["total_quantity_affected"] >= 30, body


# ================= 3) Evidence upload / list / file / delete ================= #


class TestEvidence:
    def test_upload_list_download(self, api_client, evidence_complaint):
        cid = evidence_complaint["id"]
        png = _tiny_png_bytes()
        files = {"file": ("proof.png", io.BytesIO(png), "image/png")}
        r = api_client.post(
            f"{BASE_URL}/api/complaints/{cid}/evidence",
            files=files,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("complaint_id") == cid
        assert body.get("filename") == "proof.png"
        assert body.get("mime_type", "").startswith("image/")
        assert body.get("size_bytes", 0) > 0
        eid = body["id"]
        # Save eid for later tests via class attribute
        TestEvidence._uploaded_eid = eid
        TestEvidence._uploaded_size = body["size_bytes"]

        # list
        lst = api_client.get(
            f"{BASE_URL}/api/complaints/{cid}/evidence", timeout=TIMEOUT
        )
        assert lst.status_code == 200, lst.text
        items = lst.json()
        assert isinstance(items, list)
        assert any(e["id"] == eid for e in items)

        # download
        f = api_client.get(
            f"{BASE_URL}/api/complaints/{cid}/evidence/{eid}/file", timeout=TIMEOUT
        )
        assert f.status_code == 200, f.text
        assert f.headers.get("content-type", "").startswith("image/")
        assert f.content[:8] == b"\x89PNG\r\n\x1a\n", f"bad PNG header: {f.content[:8]!r}"

    def test_upload_unsupported_ext_returns_415(self, api_client, evidence_complaint):
        cid = evidence_complaint["id"]
        files = {"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")}
        r = api_client.post(
            f"{BASE_URL}/api/complaints/{cid}/evidence",
            files=files,
            timeout=TIMEOUT,
        )
        assert r.status_code == 415, f"got {r.status_code}: {r.text[:200]}"

    def test_upload_over_10mb_returns_413(self, api_client, evidence_complaint):
        cid = evidence_complaint["id"]
        big = _large_png_bytes()
        files = {"file": ("huge.png", io.BytesIO(big), "image/png")}
        r = api_client.post(
            f"{BASE_URL}/api/complaints/{cid}/evidence",
            files=files,
            timeout=TIMEOUT,
        )
        assert r.status_code == 413, f"got {r.status_code}: {r.text[:200]}"

    def test_upload_to_missing_complaint_returns_404(self, api_client):
        png = _tiny_png_bytes()
        files = {"file": ("x.png", io.BytesIO(png), "image/png")}
        r = api_client.post(
            f"{BASE_URL}/api/complaints/9999999/evidence",
            files=files,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404, f"got {r.status_code}: {r.text[:200]}"

    def test_delete_evidence(self, api_client, evidence_complaint):
        cid = evidence_complaint["id"]
        # Upload a fresh one to delete
        png = _tiny_png_bytes()
        files = {"file": ("todelete.png", io.BytesIO(png), "image/png")}
        up = api_client.post(
            f"{BASE_URL}/api/complaints/{cid}/evidence", files=files, timeout=TIMEOUT
        )
        assert up.status_code == 200, up.text
        eid = up.json()["id"]

        d = api_client.delete(
            f"{BASE_URL}/api/complaints/{cid}/evidence/{eid}", timeout=TIMEOUT
        )
        assert d.status_code == 200, d.text
        assert d.json().get("deleted") is True

        # subsequent GET returns 404
        f = api_client.get(
            f"{BASE_URL}/api/complaints/{cid}/evidence/{eid}/file", timeout=TIMEOUT
        )
        assert f.status_code == 404, f"expected 404 got {f.status_code}"


# ================= 4) PDF grows after image evidence ================= #


class TestPdfWithEvidence:
    def test_pdf_size_increases_with_image(self, api_client):
        # Fresh complaint so we can compare sizes cleanly
        payload = {
            "complaint_source": "Portal",
            "customer_name": "TEST_PDF_Grow",
            "product_name": "Paracetamol",
            "batch_number": "TEST_PDFGROW",
            "complaint_type": "Packaging",
            "initial_severity": "Medium",
            "priority": "High",
            "complaint_description": "Broken outer carton.",
        }
        s = api_client.post(f"{BASE_URL}/api/complaints/save", json=payload, timeout=TIMEOUT)
        assert s.status_code == 200, s.text
        cid = s.json()["id"]

        # Baseline PDF, no evidence
        r1 = api_client.get(f"{BASE_URL}/api/complaints/{cid}/pdf", timeout=TIMEOUT)
        assert r1.status_code == 200, r1.text
        assert r1.content[:5] == b"%PDF-"
        base_size = len(r1.content)

        # Attach a PNG
        png = _tiny_png_bytes(64, 64)
        files = {"file": ("evidence.png", io.BytesIO(png), "image/png")}
        up = api_client.post(
            f"{BASE_URL}/api/complaints/{cid}/evidence", files=files, timeout=TIMEOUT
        )
        assert up.status_code == 200, up.text

        # PDF again after attaching image
        r2 = api_client.get(f"{BASE_URL}/api/complaints/{cid}/pdf", timeout=TIMEOUT)
        assert r2.status_code == 200, r2.text
        assert r2.content[:5] == b"%PDF-"
        new_size = len(r2.content)

        assert new_size > base_size, (
            f"Expected PDF to grow after inlining image; base={base_size} new={new_size}"
        )


# ================= 5) Recalls ================= #


class TestRecalls:
    def test_create_and_list_recall(self, api_client, evidence_complaint):
        cid = evidence_complaint["id"]
        payload = {
            "batch_number": "EV_BATCH_TEST",
            "product_name": "Amoxicillin",
            "affected_units": "50",
            "complaint_ids": [cid, 9999999],  # 2nd id doesn't exist -> silently skipped
            "reason": "Contamination trend",
            "initiated_by": "TEST_QA_Head",
        }
        r = api_client.post(f"{BASE_URL}/api/recalls", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "id" in body and isinstance(body["id"], int)
        assert body.get("status") == "Initiated"
        assert body.get("batch_number") == "EV_BATCH_TEST"

        # GET list contains it
        lst = api_client.get(f"{BASE_URL}/api/recalls", timeout=TIMEOUT)
        assert lst.status_code == 200, lst.text
        items = lst.json()
        assert isinstance(items, list)
        assert any(x.get("id") == body["id"] for x in items)

        # The associated existing complaint should now be Under Recall
        c = api_client.get(f"{BASE_URL}/api/complaints/{cid}", timeout=TIMEOUT)
        assert c.status_code == 200, c.text
        assert c.json().get("status") == "Under Recall", c.json()

    def test_create_recall_empty_batch_returns_400(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/recalls",
            json={"batch_number": "", "complaint_ids": []},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400, r.text

    def test_list_recalls_returns_list(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/recalls", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)


# ================= 6) Regression sanity ================= #


class TestRegression:
    def test_root(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/", timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json().get("service") == "complaint-intake"

    def test_history_still_works(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/complaints?limit=5", timeout=TIMEOUT)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_by_id_and_404(self, api_client, evidence_complaint):
        cid = evidence_complaint["id"]
        r = api_client.get(f"{BASE_URL}/api/complaints/{cid}", timeout=TIMEOUT)
        assert r.status_code == 200
        r404 = api_client.get(f"{BASE_URL}/api/complaints/9999999", timeout=TIMEOUT)
        assert r404.status_code == 404
