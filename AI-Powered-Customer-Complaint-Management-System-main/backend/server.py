"""FastAPI server for the Log Customer Complaint app."""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from db import (  # noqa: E402
    Complaint,
    Evidence,
    Recall,
    SessionLocal,
    get_session,
    init_db,
)
from extractor import (  # noqa: E402
    chat_about_complaint,
    parse_file,
    run_extraction,
    stream_extraction,
)
from pdf_export import build_complaint_pdf  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_DOC_EXTS = {".pdf", ".docx", ".txt", ".eml"}
ALLOWED_EVIDENCE_EXTS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".txt", ".csv", ".docx", ".xlsx",
}
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Complaint Intake API")
api = APIRouter(prefix="/api")


class ExtractedFields(BaseModel):
    complaint_source: str = ""
    customer_name: str = ""
    product_name: str = ""
    product_strength: str = ""
    batch_number: str = ""
    manufacturing_date: str = ""
    expiry_date: str = ""
    quantity_affected: str = ""
    complaint_type: str = ""
    complaint_date: str = ""
    complaint_description: str = ""
    initial_severity: str = ""
    priority: str = ""


class ExtractResponse(BaseModel):
    extracted: ExtractedFields
    error: str | None = None


class ComplaintCreate(ExtractedFields):
    status: str = Field(default="Pending Triage")


class ChatRequest(BaseModel):
    message: str
    form: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str


class DuplicateMatch(BaseModel):
    id: int
    customer_name: str | None = None
    product_name: str | None = None
    batch_number: str | None = None
    complaint_type: str | None = None
    quantity_affected: str | None = None
    status: str
    created_at: str | None = None


class DuplicateResponse(BaseModel):
    count: int
    matches: list[DuplicateMatch]
    total_quantity_affected: int = 0


class RecallCreate(BaseModel):
    batch_number: str
    product_name: str | None = None
    affected_units: str | None = None
    complaint_ids: list[int] = Field(default_factory=list)
    reason: str | None = None
    initiated_by: str | None = None


# ---------------- helpers ---------------- #


def _sum_quantities(matches: list) -> int:
    total = 0
    for m in matches:
        raw = (getattr(m, "quantity_affected", None) or "").strip()
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits:
            try:
                total += int(digits)
            except ValueError:
                pass
    return total


async def _read_source(file: UploadFile | None, text: str | None) -> str:
    src = ""
    if file is not None and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext and ext not in ALLOWED_DOC_EXTS:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")
        data = await file.read()
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds 10MB limit")
        src = parse_file(file.filename, data)
    if not src and text:
        src = text
    if not src.strip():
        raise HTTPException(status_code=400, detail="No file content or text provided")
    return src


# ---------------- routes ---------------- #


@api.get("/")
async def root():
    return {"service": "complaint-intake", "status": "ok"}


@api.post("/complaints/extract", response_model=ExtractResponse)
async def extract_complaint(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
):
    source_text = await _read_source(file, text)
    result = await run_extraction(source_text)
    return ExtractResponse(
        extracted=ExtractedFields(**result["extracted"]),
        error=result.get("error"),
    )


@api.post("/complaints/extract/stream")
async def extract_stream(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
):
    source_text = await _read_source(file, text)

    async def event_gen():
        try:
            async for event in stream_extraction(source_text):
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0)
        except Exception as exc:  # noqa: BLE001
            logger.exception("stream failed")
            yield f"data: {json.dumps({'type':'error','message':str(exc)})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@api.post("/complaints/save")
async def save_complaint(
    payload: ComplaintCreate,
    session: AsyncSession = Depends(get_session),
):
    row = Complaint(**payload.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row.to_dict()


@api.get("/complaints")
async def list_complaints(
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
):
    limit = max(1, min(limit, 100))
    result = await session.execute(
        select(Complaint).order_by(Complaint.created_at.desc()).limit(limit)
    )
    return [row.to_dict() for row in result.scalars().all()]


@api.get("/complaints/severity-summary")
async def severity_summary(
    days: int = 30,
    session: AsyncSession = Depends(get_session),
):
    """Return per-day counts of complaints by initial_severity for the last N days."""
    days = max(1, min(days, 180))
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    day_col = func.date_trunc("day", Complaint.created_at)
    stmt = (
        select(day_col.label("day"), Complaint.initial_severity, func.count().label("n"))
        .where(Complaint.created_at >= since)
        .group_by(day_col, Complaint.initial_severity)
    )
    result = await session.execute(stmt)

    buckets: dict[str, dict[str, int]] = {}
    # seed all days so the chart renders continuously
    for i in range(days):
        d = (since + timedelta(days=i)).date().isoformat()
        buckets[d] = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0, "Unset": 0}

    for day, severity, n in result.all():
        key = day.date().isoformat() if hasattr(day, "date") else str(day)[:10]
        if key not in buckets:
            buckets[key] = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0, "Unset": 0}
        sev = severity if severity in ("Low", "Medium", "High", "Critical") else "Unset"
        buckets[key][sev] = int(n)

    series = [{"date": d, **counts} for d, counts in sorted(buckets.items())]
    totals = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0, "Unset": 0}
    for row in series:
        for k in totals:
            totals[k] += row[k]
    return {"days": days, "series": series, "totals": totals}


@api.get("/complaints/duplicate-check", response_model=DuplicateResponse)
async def duplicate_check(
    batch: str,
    session: AsyncSession = Depends(get_session),
):
    batch = (batch or "").strip()
    if not batch:
        return DuplicateResponse(count=0, matches=[], total_quantity_affected=0)
    stmt = (
        select(Complaint)
        .where(func.lower(Complaint.batch_number) == batch.lower())
        .order_by(Complaint.created_at.desc())
        .limit(20)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    matches = [
        DuplicateMatch(
            id=r.id,
            customer_name=r.customer_name,
            product_name=r.product_name,
            batch_number=r.batch_number,
            complaint_type=r.complaint_type,
            quantity_affected=r.quantity_affected,
            status=r.status,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
    return DuplicateResponse(
        count=len(matches),
        matches=matches,
        total_quantity_affected=_sum_quantities(rows),
    )


@api.get("/complaints/{complaint_id}")
async def get_complaint(
    complaint_id: int,
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(Complaint, complaint_id)
    if not row:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return row.to_dict()


@api.get("/complaints/{complaint_id}/pdf")
async def download_pdf(complaint_id: int):
    async with SessionLocal() as session:
        row = await session.get(Complaint, complaint_id)
        if not row:
            raise HTTPException(status_code=404, detail="Complaint not found")
        data = row.to_dict()
        ev_stmt = (
            select(Evidence)
            .where(Evidence.complaint_id == complaint_id)
            .order_by(Evidence.created_at.asc())
        )
        ev_rows = (await session.execute(ev_stmt)).scalars().all()
        evidence = [
            {**e.to_dict(), "storage_path": e.storage_path} for e in ev_rows
        ]
    pdf_bytes = build_complaint_pdf(data, evidence=evidence)
    filename = f"complaint-{complaint_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------- Evidence ---------------- #


@api.post("/complaints/{complaint_id}/evidence")
async def upload_evidence(
    complaint_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    complaint = await session.get(Complaint, complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    filename = file.filename or "attachment"
    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in ALLOWED_EVIDENCE_EXTS:
        raise HTTPException(status_code=415, detail=f"Unsupported evidence type: {ext}")

    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10MB limit")

    complaint_dir = UPLOAD_DIR / str(complaint_id)
    complaint_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = complaint_dir / stored_name
    path.write_bytes(data)

    mime = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    row = Evidence(
        complaint_id=complaint_id,
        filename=filename,
        mime_type=mime,
        size_bytes=len(data),
        storage_path=str(path),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row.to_dict()


@api.get("/complaints/{complaint_id}/evidence")
async def list_evidence(
    complaint_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Evidence)
        .where(Evidence.complaint_id == complaint_id)
        .order_by(Evidence.created_at.asc())
    )
    result = await session.execute(stmt)
    return [e.to_dict() for e in result.scalars().all()]


@api.get("/complaints/{complaint_id}/evidence/{evidence_id}/file")
async def get_evidence_file(
    complaint_id: int,
    evidence_id: int,
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(Evidence, evidence_id)
    if not row or row.complaint_id != complaint_id:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if not os.path.exists(row.storage_path):
        raise HTTPException(status_code=410, detail="Evidence file missing on disk")
    return FileResponse(
        row.storage_path,
        media_type=row.mime_type,
        filename=row.filename,
    )


@api.delete("/complaints/{complaint_id}/evidence/{evidence_id}")
async def delete_evidence(
    complaint_id: int,
    evidence_id: int,
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(Evidence, evidence_id)
    if not row or row.complaint_id != complaint_id:
        raise HTTPException(status_code=404, detail="Evidence not found")
    try:
        if os.path.exists(row.storage_path):
            os.remove(row.storage_path)
    except OSError:
        pass
    await session.delete(row)
    await session.commit()
    return {"deleted": True, "id": evidence_id}


# ---------------- Recalls ---------------- #


@api.post("/recalls")
async def create_recall(
    payload: RecallCreate,
    session: AsyncSession = Depends(get_session),
):
    batch = payload.batch_number.strip()
    if not batch:
        raise HTTPException(status_code=400, detail="batch_number is required")
    row = Recall(
        batch_number=batch,
        product_name=payload.product_name,
        affected_units=payload.affected_units,
        complaint_ids=",".join(str(i) for i in (payload.complaint_ids or [])) or None,
        reason=payload.reason,
        initiated_by=payload.initiated_by,
    )
    session.add(row)

    # Mark associated complaints as "Under Recall"
    if payload.complaint_ids:
        for cid in payload.complaint_ids:
            c = await session.get(Complaint, cid)
            if c:
                c.status = "Under Recall"
    else:
        # fallback: mark all complaints on this batch
        stmt = select(Complaint).where(
            func.lower(Complaint.batch_number) == batch.lower()
        )
        for c in (await session.execute(stmt)).scalars().all():
            c.status = "Under Recall"

    await session.commit()
    await session.refresh(row)
    return row.to_dict()


@api.get("/recalls")
async def list_recalls(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Recall).order_by(Recall.created_at.desc()).limit(50)
    )
    return [r.to_dict() for r in result.scalars().all()]


# ---------------- Chat ---------------- #


@api.post("/complaints/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    reply = await chat_about_complaint(req.message, req.form)
    return ChatResponse(reply=reply)


@app.get("/")
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "complaint-intake-api"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.on_event("startup")
async def _startup() -> None:
    await init_db()
    logger.info("Database initialised")
