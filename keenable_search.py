"""Keenable search for FacetimeFriend (drop next to main.py as keenable_search.py).

Contract used by search.py:
    async search_for(args: dict) -> list[{"query", "title", "url", "snippet"}]

Setup:
    export KEENABLE_API_KEY=keen_...      # from keenable.ai/console
    export SEARCH_TIMEOUT_S=7             # page fetches for prices need a bit more time
    USE_MOCK=0 uvicorn main:app --port 8000 --reload

Without a key it falls back to Keenable's keyless public endpoints (rate limited).
"""
from __future__ import annotations

import asyncio
import os
import re

import httpx

from search import build_queries  # same queries the rules expect ("official", "scam", "price"...)

API_URL = os.getenv("KEENABLE_API_URL", "https://api.keenable.ai")
API_KEY = os.getenv("KEENABLE_API_KEY", "").strip()
MODE = os.getenv("KEENABLE_MODE", "realtime")        # "realtime" = fastest, "pro" = deeper
MAX_RESULTS = int(os.getenv("KEENABLE_MAX_RESULTS", "5"))
PER_QUERY_TIMEOUT_S = float(os.getenv("KEENABLE_TIMEOUT_S", "3.5"))
FETCH_TIMEOUT_S = float(os.getenv("KEENABLE_FETCH_TIMEOUT_S", "3"))
MAX_PRICE_FETCHES = int(os.getenv("KEENABLE_MAX_PRICE_FETCHES", "4"))
MIN_PLAUSIBLE_PRICE = float(os.getenv("MIN_PLAUSIBLE_PRICE", "20"))  # skips "$5 off", "$9.99 shipping"

PRICE_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?")


def _headers() -> dict:
    return {"X-API-Key": API_KEY} if API_KEY else {"X-Keenable-Title": "FacetimeFriend"}


def _path(name: str) -> str:
    return f"{API_URL}/v1/{name}" if API_KEY else f"{API_URL}/v1/{name}/public"


def _has_price(text: str) -> bool:
    return bool(PRICE_RE.search(text or ""))


NOT_A_PRICE_RE = re.compile(r"(?:over|shipping|off|save|saving|discount|credit|reward|gift card|up to|from)\W*$", re.I)


def _page_price(content: str) -> float | None:
    """First plausible $ price near the top of a product page, skipping
    promo amounts such as "free shipping over $35" or "$5 off"."""
    text = (content or "")[:6000]
    for m in PRICE_RE.finditer(text):
        before = text[max(0, m.start() - 25):m.start()]
        after = text[m.end():m.end() + 6].lower()
        if NOT_A_PRICE_RE.search(before) or after.lstrip().startswith("off"):
            continue
        whole, cents = m.group(1), m.group(2)
        value = float(whole.replace(",", "") + ("." + cents if cents else ""))
        if MIN_PLAUSIBLE_PRICE <= value <= 20000:
            return value
    return None


async def _search(client: httpx.AsyncClient, query: str) -> list[dict]:
    body = {"query": query, "mode": MODE, "max_results": MAX_RESULTS,
            "snippet_max_length": 1200 if "price" in query.lower() else 400}
    try:
        r = await client.post(_path("search"), headers=_headers(), json=body, timeout=PER_QUERY_TIMEOUT_S)
        r.raise_for_status()
        hits = r.json().get("results", [])
    except Exception as e:
        print(f"keenable search failed ({query!r}):", repr(e))
        return []
    out = []
    for h in hits:
        # rules.py reads title + snippet; include the description so prices and
        # scam mentions in either field are found
        text = " ".join(x for x in (h.get("description"), h.get("snippet")) if x)
        out.append({"query": query, "title": h.get("title", ""), "url": h.get("url", ""),
                    "snippet": text[:1500]})
    return out


async def _fetch_price(client: httpx.AsyncClient, url: str) -> float | None:
    try:
        r = await client.get(_path("fetch"), headers=_headers(), params={"url": url},
                             timeout=FETCH_TIMEOUT_S)
        r.raise_for_status()
        return _page_price(r.json().get("content", ""))
    except Exception as e:
        print(f"keenable fetch failed ({url}):", repr(e))
        return None


async def _enrich_prices(client: httpx.AsyncClient, results: list[dict]) -> None:
    """For price results whose snippet has no $ amount, read the price off the page."""
    todo = [r for r in results
            if "price" in r["query"].lower() and r["url"]
            and not _has_price(r["title"] + " " + r["snippet"])][:MAX_PRICE_FETCHES]
    prices = await asyncio.gather(*(_fetch_price(client, r["url"]) for r in todo))
    for r, p in zip(todo, prices):
        if p:
            r["snippet"] = f"Price ${p:.2f}. " + r["snippet"]


async def search_for(args: dict) -> list[dict]:
    queries = [q for q in build_queries(args) if q and q.strip()]
    async with httpx.AsyncClient() as client:
        batches = await asyncio.gather(*(_search(client, q) for q in queries))
        results = [hit for batch in batches for hit in batch]
        if (args.get("category") or "").lower() == "product":
            await _enrich_prices(client, results)
    return results


if __name__ == "__main__":  # manual test: python keenable_search.py contracts/check_item_args_product.json
    import json
    import pathlib
    import sys
    import time

    path = sys.argv[1] if len(sys.argv) > 1 else "contracts/check_item_args.json"
    args = json.loads(pathlib.Path(path).read_text())
    t = time.perf_counter()
    hits = asyncio.run(search_for(args))
    for hit in hits:
        price = PRICE_RE.search(hit["title"] + " " + hit["snippet"]) if "price" in hit["query"].lower() else None
        tag = f"  -> {price.group(0)}" if price else ""
        print(f"[{hit['query']}] {hit['title'][:70]} | {hit['url']}{tag}")
    print(f"\n{len(hits)} results in {time.perf_counter() - t:.1f}s")