# PART 1
from __future__ import annotations

import io
import json
import logging
import os
import re
from typing import TypedDict

from groq import Groq
from langgraph.graph import END, StateGraph
from pypdf import PdfReader
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

FIELD_KEYS = [
    "complaint_source",
    "customer_name",
    "product_name",
    "product_strength",
    "batch_number",
    "manufacturing_date",
    "expiry_date",
    "quantity_affected",
    "complaint_type",
    "complaint_date",
    "complaint_description",
    "initial_severity",
    "priority",
]

EMPTY_EXTRACTION = {k: "" for k in FIELD_KEYS}

SYSTEM_PROMPT = """
You are an expert pharmaceutical QA analyst.

Extract ONLY JSON.

Return exactly these keys:

complaint_source
customer_name
product_name
product_strength
batch_number
manufacturing_date
expiry_date
quantity_affected
complaint_type
complaint_date
complaint_description
initial_severity
priority

Return ONLY valid JSON.

If missing use "".

Severity:
Low
Medium
High
Critical

Priority:
Low
Medium
High
Urgent
"""

def _parse_pdf(data):
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def _parse_docx(data):
    doc = DocxDocument(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)

def parse_file(filename, data):
    name = (filename or "").lower()

    if name.endswith(".pdf"):
        return _parse_pdf(data)

    if name.endswith(".docx"):
        return _parse_docx(data)

    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def _coerce_json(raw):
    if not raw:
        return {}

    fenced = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        raw,
        re.DOTALL,
    )

    if fenced:
        raw = fenced.group(1)

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1:
        return {}

    try:
        return json.loads(raw[start:end+1])
    except Exception:
        return {}

class ExtractionState(TypedDict, total=False):
    source_text: str
    llm_raw: str
    extracted: dict
    error: str

async def ingest_node(state):

    text = (state.get("source_text") or "").strip()

    if not text:
        return {
            **state,
            "error": "empty_input",
            "extracted": EMPTY_EXTRACTION.copy(),
        }

    return {
        **state,
        "source_text": text[:16000],
    }
async def llm_node(state):
    if state.get("error"):
        return state

    if not client:
        return {
            **state,
            "error": "missing_groq_key",
            "extracted": EMPTY_EXTRACTION.copy(),
        }

    try:
        prompt = f"""
{SYSTEM_PROMPT}

Extract complaint fields from the following complaint.

{state["source_text"]}
"""

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
        )

        return {
            **state,
            "llm_raw": response.choices[0].message.content,
        }

    except Exception as exc:
        logger.exception(exc)

        return {
            **state,
            "error": f"llm_error: {exc}",
            "extracted": EMPTY_EXTRACTION.copy(),
        }


async def parse_node(state):
    if state.get("error"):
        return state

    parsed = _coerce_json(state.get("llm_raw", ""))

    merged = EMPTY_EXTRACTION.copy()

    for key in merged:
        value = parsed.get(key, "")
        merged[key] = "" if value is None else str(value).strip()

    return {
        **state,
        "extracted": merged,
    }


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
    result = await _graph.ainvoke(
        {
            "source_text": text,
        }
    )

    return {
        "extracted": result.get(
            "extracted",
            EMPTY_EXTRACTION.copy(),
        ),
        "error": result.get("error"),
    }


async def stream_extraction(text):
    text = (text or "").strip()

    if not text:
        yield {
            "type": "error",
            "message": "empty_input",
        }
        return

    if not client:
        yield {
            "type": "error",
            "message": "missing_groq_key",
        }
        return

    yield {
        "type": "start",
    }

    try:
        prompt = f"""
{SYSTEM_PROMPT}

Extract complaint fields from the following complaint.

{text[:16000]}
"""

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
        )

        full = _coerce_json(
            response.choices[0].message.content
        )

    except Exception as exc:
        logger.exception(exc)

        yield {
            "type": "error",
            "message": f"llm_error: {exc}",
        }
        return

    for key in FIELD_KEYS:
        value = ""

        if isinstance(full, dict):
            value = full.get(key, "")

        yield {
            "type": "field",
            "key": key,
            "value": "" if value is None else str(value).strip(),
        }

    yield {
        "type": "done",
    }

async def chat_about_complaint(user_message, form_state):
    if not client:
        return "Groq API key not configured."

    context = json.dumps(
        form_state or {},
        indent=2,
    )

    prompt = f"""
You are a pharmaceutical QA Complaint Intake Assistant.

You help users complete complaint forms.

Current Complaint Form:

{context}

User Question:

{user_message}

Instructions:
- Answer professionally.
- Use the complaint form information whenever relevant.
- If information is missing, tell the user politely.
- Keep answers concise.
"""

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful pharmaceutical QA complaint assistant.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.3,
            max_tokens=1024,
        )

        return response.choices[0].message.content

    except Exception as exc:
        logger.exception(exc)
        return f"Sorry, an error occurred: {exc}"    
