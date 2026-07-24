# Log Customer Complaint — Single-page App

## Problem statement
Single-page pharmaceutical QA complaint intake form. Left side (70%) is a numbered
4-section form (Origin & Customer Details, Product & Batch Identification, Complaint
Details, Initial Assessment & Priority). Right side (30%) is an AI Complaint Intake
Assistant with drag-drop file upload, paste-text button, animated extraction progress,
AI message card, and chat input. Data extracted from PDF/DOCX/TXT/EML or pasted text
and used to auto-populate the form. Save button persists complaint.

## Tech stack (as chosen)
- Frontend: React 19 (CRA) + Tailwind + shadcn/ui + Redux Toolkit + Axios
- Backend: FastAPI (async) + SQLAlchemy + asyncpg
- DB: PostgreSQL 15 (installed locally in pod, managed by supervisor as `postgresql`)
- AI: LangGraph pipeline (ingest → llm → parse) using Emergent Universal LLM Key
  with Gemini 2.5 Flash (user-provided Gemini key stored in env but has zero quota;
  the Groq/llama request in the original spec was substituted since the provided key
  is a Gemini key and Emergent Universal Key doesn’t proxy Groq).

## Implemented (2026-07-23)
- Postgres server, `complaint_db` database, `complaint_user` role
- `POST /api/complaints/extract` — file upload OR pasted text → LangGraph → JSON fields
- `POST /api/complaints/save` — writes complaint to Postgres
- `GET /api/complaints` — list last 50
- `POST /api/complaints/chat` — grounded chat over current form
- Redux slice for form/extraction/chat state
- ComplaintPage 70/30 grid, matches screenshot
- Drag-drop upload, animated progress bar, AI assistant chat card
- Save/Reset with sonner toasts

## Iteration 2 (2026-07-23)
- **Complaint History drawer** — shadcn Sheet showing last 10 saved complaints with severity badge and PDF button
- **Live Extraction Stream** — `POST /api/complaints/extract/stream` (SSE) streaming per-field events; Redux updates each field as it arrives; progress driven by number of fields seen
- **PDF Export** — `GET /api/complaints/{id}/pdf` (ReportLab) with QA-styled sections and signature blocks
- **Duplicate Detector** — `GET /api/complaints/duplicate-check?batch=X` + inline amber warning under Batch/Lot Number with previous complaint refs
- 23/23 backend tests passing (iteration_1 + iteration_2)

## Iteration 3 (2026-07-23)
- **Attach Evidence** — new `evidence` table + endpoints: `POST/GET /api/complaints/{id}/evidence`, `GET/DELETE /api/complaints/{id}/evidence/{eid}/file`. UI Section 5 (dropzone + file list + delete) appears in the form only after Save Complaint. Images are inlined into the PDF export appendix.
- **Severity Heatmap** — `GET /api/complaints/severity-summary?days=30`. Recharts stacked mini bar chart (Low/Medium/High/Critical) mounted at the top of the History drawer.
- **Recall Trigger** — new `recalls` table + `POST /api/recalls` (creates record, flips complaint statuses to "Under Recall"), `GET /api/recalls`. Duplicate warning turns red at ≥3 hits, exposes "Initiate Batch Recall" button; dialog prefilled with batch, product, auto-summed affected units, and included complaint ids.
- Duplicate-check response now includes `total_quantity_affected`.
- 39/39 backend tests passing (iteration_1 + iteration_2 + iteration_3), 12/12 retest confirms PDF fix.

## Backlog / P1
- Extraction status streaming (SSE)
- Real severity/priority validation rules

## Backlog / P2
- Export saved complaints to CSV/PDF
- Multi-file batch extraction
