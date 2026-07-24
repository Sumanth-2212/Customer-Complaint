"""Gemini-powered extractor using google-genai."""
from __future__ import annotations
import io, json, logging, os, re
from typing import Any, AsyncGenerator, TypedDict
from google import genai
from google.genai import types
from langgraph.graph import END, StateGraph
from pypdf import PdfReader
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("EMERGENT_LLM_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-2.5-flash")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

FIELD_KEYS = ["complaint_source","customer_name","product_name","product_strength","batch_number","manufacturing_date","expiry_date","quantity_affected","complaint_type","complaint_date","complaint_description","initial_severity","priority"]
EMPTY_EXTRACTION = {k: "" for k in FIELD_KEYS}
SYSTEM_PROMPT = """You are an expert pharmaceutical QA intake analyst. Extract a JSON object with these exact keys: complaint_source, customer_name, product_name, product_strength, batch_number, manufacturing_date, expiry_date, quantity_affected, complaint_type, complaint_date, complaint_description, initial_severity (Low/Medium/High/Critical), priority (Low/Medium/High/Urgent). Return ONLY valid JSON, no markdown."""

def _parse_pdf(data):
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)

def _parse_docx(data):
    doc = DocxDocument(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)

def parse_file(filename, data):
    name = (filename or "").lower()
    if name.endswith(".pdf"): return _parse_pdf(data)
    if name.endswith(".docx"): return _parse_docx(data)
    try: return data.decode("utf-8", errors="ignore")
    except: return ""

def _coerce_json(raw):
    if not raw: return {}
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced: raw = fenced.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start: return {}
    try: return json.loads(raw[start:end+1])
    except: return {}

class ExtractionState(TypedDict, total=False):
    source_text: str
    llm_raw: str
    extracted: dict
    error: str

async def ingest_node(state):
    text = (state.get("source_text") or "").strip()
    if not text: return {**state, "error": "empty_input", "extracted": EMPTY_EXTRACTION.copy()}
    return {**state, "source_text": text[:16000]}

async def llm_node(state):
    if state.get("error"): return state
    if not client: return {**state, "error": "missing_llm_key", "extracted": EMPTY_EXTRACTION.copy()}
    prompt = SYSTEM_PROMPT + f"\n\nTEXT:\n{state['source_text']}"
    try:
        response = client.models.generate_content(model=LLM_MODEL, contents=prompt)
        return {**state, "llm_raw": response.text}
    except Exception as exc:
        return {**state, "error": f"llm_error: {exc}", "extracted": EMPTY_EXTRACTION.copy()}

async def parse_node(state):
    if state.get("error"): return state
    parsed = _coerce_json(state.get("llm_raw", ""))
    merged = EMPTY_EXTRACTION.copy()
    for key in merged:
        val = parsed.get(key, "")
        merged[key] = "" if val is None else str(val).strip()
    return {**state, "extracted": merged}

def build_graph():
    graph = StateGraph(ExtractionState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("llm", llm_node)
    graph.add_node("parse", parse_node)
    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "llm")
    graph.add_edge("llm", "parse")
    graph.add_edge("parse", END)
    return graph.compile()

_graph = build_graph()

async def run_extraction(text):
    result = await _graph.ainvoke({"source_text": text})
    return {"extracted": result.get("extracted", EMPTY_EXTRACTION.copy()), "error": result.get("error")}

async def stream_extraction(text):
    text = (text or "").strip()
    if not text: yield {"type": "error", "message": "empty_input"}; return
    if not client: yield {"type": "error", "message": "missing_llm_key"}; return
    yield {"type": "start"}
    prompt = SYSTEM_PROMPT + f"\n\nRespond with JSON keys in this order: {', '.join(FIELD_KEYS)}.\n\nTEXT:\n{text[:16000]}"
    try:
        response = client.models.generate_content(model=LLM_MODEL, contents=prompt)
        full = _coerce_json(response.text)
    except Exception as exc:
        yield {"type": "error", "message": f"llm_error: {exc}"}; return
    for k in FIELD_KEYS:
        v = full.get(k, "") if isinstance(full, dict) else ""
        yield {"type": "field", "key": k, "value": "" if v is None else str(v).strip()}
    yield {"type": "done"}

async def chat_about_complaint(user_message, form_state):
    if not client: return "AI assistant not configured. Please set GEMINI_API_KEY."
    context = json.dumps(form_state or {}, indent=2)
    prompt = f"You are a QA complaint intake assistant.\n\nForm:\n{context}\n\nQuestion:\n{user_message}"
    try:
        response = client.models.generate_content(model=LLM_MODEL, contents=prompt)
        return response.text
    except Exception as exc:
        return f"Sorry, error: {exc}"
