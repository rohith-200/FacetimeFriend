"""Parse a texted message into check_item args (the exact-URL iMessage path)."""
from __future__ import annotations

import re

from rules import base_domain, host_of, normalize_variants

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+|\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?:/[^\s<>\"']*)?")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
CAP_WORD_RE = re.compile(r"\b[A-Z][A-Za-z0-9&]{2,}\b")
TRAIL = ".,;:!?)]}'\""


def _dedupe(items):
    return list(dict.fromkeys(items))


def parse_message(text: str) -> dict:
    emails = _dedupe(EMAIL_RE.findall(text))
    no_emails = EMAIL_RE.sub(" ", text)
    urls = _dedupe(u.rstrip(TRAIL) for u in URL_RE.findall(no_emails))
    phones = _dedupe(p.strip() for p in PHONE_RE.findall(text))
    return {"urls": urls, "emails": emails, "phones": phones}


def guess_company(text: str, domains: list[str]) -> str | None:
    """'Amazon' in the text + 'amaz0n-careers.com' -> 'Amazon'."""
    labels = [base_domain(host_of(d)).split(".")[0] for d in domains]
    variants = {v for lbl in labels for v in normalize_variants(lbl)} | set(labels)
    for word in CAP_WORD_RE.findall(text):
        w = word.lower()
        if len(w) >= 4 and any(w in v for v in variants):
            return word
    return None


def message_to_args(text: str) -> dict:
    found = parse_message(text)
    return {
        "category": "scam",
        "item": "Texted message: " + text.strip().replace("\n", " ")[:60],
        "claimed_company": guess_company(text, found["urls"] + found["emails"]),
        **found,
        "price_seen": None,
        "red_flags_seen": [text],  # rules scan this for fees, SSN, urgency...
        "question": "Is this message legit?",
    }
