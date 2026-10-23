"""
FacetimeFriend backend (Person 2). Setup version: endpoints work with MOCK results,
so Person 1 (Chert/LiveKit) and Person 3 (dashboard) can build against them right away.

Run:  uvicorn server:app --port 8000 --reload
Tunnel: cloudflared tunnel --url http://localhost:8000
"""
import base64
import json
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

CONTRACTS = Path(__file__).parent / "contracts"

app = FastAPI(title="FacetimeFriend backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# What the dashboard polls. Updated after every pipeline step.
STATE: dict = {"status": "idle", "step": None, "updated_at": None, "understanding": None,
               "verification": None, "result": None, "frame_b64": None}


def set_state(**kw):
    STATE.update(kw, updated_at=time.time())


async def run_pipeline(image: bytes | None, text: str = "", question: str = "") -> dict:
    """Single entry point for BOTH the LiveKit check_item tool and /analyze.
    Setup version returns mock data; real steps get swapped in during the build."""
    set_state(status="running", step="understand", result=None,
              frame_b64=base64.b64encode(image).decode() if image else None)
    understanding = json.loads((CONTRACTS / "understanding.json").read_text())   # TODO: understand()
    set_state(step="verify", understanding=understanding)
    verification = json.loads((CONTRACTS / "verification.json").read_text())    # TODO: plan() + verify()
    set_state(step="evaluate", verification=verification)
    result = json.loads((CONTRACTS / "result_scam.json").read_text())           # TODO: evaluate()
    set_state(status="done", step="done", result=result)
    return result


class AnalyzeJSON(BaseModel):
    image_base64: str | None = None
    image_url: str | None = None
    text: str = ""
    question: str = ""
    source: str = "imessage"
    user_phone: str | None = None


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/analyze")
async def analyze_json(body: AnalyzeJSON):
    """JSON input: base64 image, an image URL to download (e.g. a Chert attachment), or text only."""
    image = None
    if body.image_base64:
        image = base64.b64decode(body.image_base64)
    elif body.image_url:
        async with httpx.AsyncClient(timeout=20) as c:
            image = (await c.get(body.image_url)).content
    return await run_pipeline(image, body.text, body.question)


@app.post("/analyze/upload")
async def analyze_upload(file: UploadFile = File(...), question: str = Form(""), text: str = Form("")):
    """Multipart input: for the fallback upload page and quick curl tests."""
    return await run_pipeline(await file.read(), text, question)


@app.get("/latest")
async def latest():
    return STATE
