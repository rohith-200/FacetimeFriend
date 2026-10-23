"""FacetimeFriend backend (Person 2).

Run:     uvicorn main:app --port 8000 --reload
Tunnel:  cloudflared tunnel --url http://localhost:8000
"""
from __future__ import annotations

import time
import traceback
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from parser import message_to_args
from rules import evaluate, fallback_result
from search import get_results

app = FastAPI(title="FacetimeFriend backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class CheckItemArgs(BaseModel):
    category: str = "other"
    item: str = ""
    claimed_company: str | None = None
    urls: list[str] = []
    emails: list[str] = []
    phones: list[str] = []
    price_seen: Any = None
    red_flags_seen: list[str] = []
    question: str = ""

    @field_validator("category", mode="before")
    @classmethod
    def clean_category(cls, v):
        v = str(v or "other").strip().lower()
        return v if v in {"scam", "product", "other"} else "other"

    @field_validator("urls", "emails", "phones", "red_flags_seen", mode="before")
    @classmethod
    def listify(cls, v):  # the agent may send a string or null instead of a list
        if v is None:
            return []
        return [v] if isinstance(v, str) else v


class TextIn(BaseModel):
    text: str


# ------------------------------------------------ live state for the dashboard
LATEST: dict = {"check_id": 0, "status": "idle", "steps": [], "args": None,
                "queries": [], "searches": [], "search_source": None, "result": None}
_t0 = 0.0


def start_check(args: dict):
    global _t0
    _t0 = time.perf_counter()
    LATEST.update(check_id=LATEST["check_id"] + 1, status="running", steps=[], args=args,
                  queries=[], searches=[], search_source=None, result=None)
    step("received")


def step(name: str, **data):
    LATEST["steps"].append({"step": name, "ms": round((time.perf_counter() - _t0) * 1000), **data})


async def run_check(args: dict) -> dict:
    start_check(args)
    try:
        step("searching")
        results, source = await get_results(args)
        LATEST.update(searches=results, search_source=source,
                      queries=list(dict.fromkeys(r.get("query", "") for r in results)))
        step("searched", source=source, count=len(results))
        result = evaluate(args, results)
        step("rules_applied", flags=result["rule_flags"])
        step("verdict", verdict=result["suggested_verdict"])
        LATEST.update(result=result, status="done")
    except Exception as e:
        traceback.print_exc()
        result = fallback_result(args, repr(e))
        step("error", error=repr(e))
        LATEST.update(result=result, status="error")
    return result


# ------------------------------------------------ endpoints
@app.get("/health")
def health():
    return {"ok": True}


@app.post("/verify")
async def verify(args: CheckItemArgs):
    return await run_check(args.model_dump())


@app.post("/verify_text")
async def verify_text(body: TextIn):
    """For Person 1's iMessage webhook: raw texted message in, result out."""
    return await run_check(message_to_args(body.text))


@app.get("/latest")
def latest():
    return LATEST
