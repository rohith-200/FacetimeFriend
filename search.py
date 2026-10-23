"""Search layer: mock data now, Person 3's Keenable module later.

CONTRACT WITH PERSON 3 (agree at 12:15):
    keenable_search.search_for(args: dict) -> list[dict]   (sync or async)
    each dict: {"query": str, "title": str, "url": str, "snippet": str}
The "query" field matters: rules.py uses it to tell the official-site,
scam-report, price and counterfeit searches apart.

Env vars:
    USE_MOCK=1          use the fake results below (default)
    USE_MOCK=0          call keenable_search.search_for
    SEARCH_TIMEOUT_S=4  after this, fall back to cache/search_cache.json
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import pathlib

from rules import base_domain, host_of

USE_MOCK = os.getenv("USE_MOCK", "1") == "1"
SEARCH_TIMEOUT_S = float(os.getenv("SEARCH_TIMEOUT_S", "4"))
CACHE_PATH = pathlib.Path(__file__).parent / "cache" / "search_cache.json"


def first_domain(args: dict) -> str | None:
    for v in (args.get("urls") or []) + (args.get("emails") or []):
        d = base_domain(host_of(v))
        if d:
            return d
    return None


def build_queries(args: dict) -> list[str]:
    """The query table from the plan. Share with Person 3 so you match."""
    cat = (args.get("category") or "other").lower()
    company = args.get("claimed_company")
    item = args.get("item") or ""
    if cat == "scam":
        qs = []
        if company:
            qs.append(f"{company} official website")
        dom = first_domain(args)
        qs.append(f"{dom} scam" if dom else f"{company} job offer scam")
        if args.get("phones"):
            qs.append(f"{args['phones'][0]} scam")
        return qs[:3]
    if cat == "product":
        return [f"{item} price USD", f"{item} counterfeit how to spot", f"{item} reviews"]
    return [item]


# ---------------------------------------------------------------- mock data
# FAKE results for building and testing before Keenable is wired in.
def mock_search(args: dict) -> list[dict]:
    cat = (args.get("category") or "other").lower()
    q = build_queries(args)
    if cat == "scam":
        dom = first_domain(args) or "amaz0n-careers.com"
        return [
            {"query": q[0], "title": "Amazon.jobs: Careers at Amazon",
             "url": "https://www.amazon.jobs/", "snippet": "Search open jobs at Amazon and apply online."},
            {"query": q[0], "title": "Amazon.com", "url": "https://www.amazon.com/",
             "snippet": "Online shopping from Earth's biggest selection."},
            {"query": q[1] if len(q) > 1 else q[0],
             "title": f"Warning: fake recruiters using {dom}",
             "url": "https://example.org/mock-scam-report",
             "snippet": f"Several people reported {dom} as a job scam asking for an equipment fee."},
        ]
    if cat == "product":
        return [
            {"query": q[0], "title": "Eau de Parfum 100ml", "url": "https://example.com/store-a",
             "snippet": "In stock. $155.00 free shipping."},
            {"query": q[0], "title": "Eau de Parfum 100 ml spray", "url": "https://example.com/store-b",
             "snippet": "Now $149.99, was $165."},
            {"query": q[0], "title": "Perfume 100ml", "url": "https://example.com/store-c",
             "snippet": "Price: $162"},
            {"query": q[1], "title": "How to spot a fake perfume", "url": "https://example.com/spot-fakes",
             "snippet": "Check that the batch code on the box matches the bottle. Fakes often have loose cellophane."},
            {"query": q[1], "title": "Counterfeit fragrance guide", "url": "https://example.com/guide",
             "snippet": "Look for a clear, even liquid and a heavy, well-finished cap."},
            {"query": q[2], "title": "Reviews", "url": "https://example.com/reviews",
             "snippet": "Long-lasting, fresh scent. 4.6 out of 5."},
        ]
    return [{"query": q[0], "title": "Example result", "url": "https://example.com/",
             "snippet": "A general description of the item."}]


# ---------------------------------------------------------------- cache
def _keys(args: dict) -> list[str]:
    cat = (args.get("category") or "other").lower()
    name = (args.get("claimed_company") or args.get("item") or "").lower().strip()
    return [f"{cat}:{name}", cat]


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text())
    except Exception:
        return {}


def _save_cache(args: dict, results: list[dict]) -> None:
    try:
        cache = _load_cache()
        for k in _keys(args):
            cache[k] = results
        CACHE_PATH.parent.mkdir(exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        print("cache write failed:", e)


# ---------------------------------------------------------------- entry point
async def get_results(args: dict) -> tuple[list[dict], str]:
    """Returns (results, source) where source is mock | live | cache | none."""
    if USE_MOCK:
        return mock_search(args), "mock"
    try:
        from keenable_search import search_for  # Person 3's module
        if inspect.iscoroutinefunction(search_for):
            results = await asyncio.wait_for(search_for(args), SEARCH_TIMEOUT_S)
        else:
            results = await asyncio.wait_for(asyncio.to_thread(search_for, args), SEARCH_TIMEOUT_S)
        if results:
            _save_cache(args, results)
            return results, "live"
    except Exception as e:
        print("live search failed, using cache:", repr(e))
    cache = _load_cache()
    for k in _keys(args):
        if cache.get(k):
            return cache[k], "cache"
    return [], "none"
