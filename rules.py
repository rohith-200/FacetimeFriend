"""FacetimeFriend verification rules (Person 2).

Pure functions only, no network, so everything here is unit-testable.
Input:  the check_item args (dict) + a flat list of search results:
        [{"query": str, "title": str, "url": str, "snippet": str}, ...]
Output: the /verify response dict (see contracts/verify_result.json).
"""
from __future__ import annotations

import re
import statistics
from urllib.parse import urlparse

# ---------------------------------------------------------------- constants
FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "aol.com", "icloud.com", "proton.me", "protonmail.com",
}
COMPANY_FILLER = {"inc", "llc", "ltd", "corp", "corporation", "company", "co",
                  "hr", "careers", "recruiting", "recruitment", "team", "support", "the"}

RISKY_PATTERNS = {
    "upfront_fee": r"\bfees?\b|\bdeposit\b|pay (?:for|upfront|in advance)",
    "gift_cards": r"gift ?cards?",
    "crypto": r"crypto|bitcoin|\bbtc\b|usdt|ethereum",
    "wire_transfer": r"wire (?:transfer|money)|western union|moneygram|zelle|cash ?app",
    "asks_for_ssn": r"\bssn\b|social security",
    "asks_for_bank_details": r"bank (?:details|account|info)|routing number|account number",
    "asks_for_password": r"password|one[- ]time (?:code|pin)|\botp\b|verification code|2fa code",
}
RISKY_REASONS = {
    "upfront_fee": "It asks you to pay a fee up front",
    "gift_cards": "It asks for payment in gift cards",
    "crypto": "It asks for payment in crypto",
    "wire_transfer": "It asks for a wire or app transfer",
    "asks_for_ssn": "It asks for your Social Security number",
    "asks_for_bank_details": "It asks for your bank details",
    "asks_for_password": "It asks for a password or login code",
}
URGENCY_RE = re.compile(
    r"within \d+\s*(?:hours?|hrs?|minutes?|mins?)|\b\d+[- ]?(?:hours?|hrs?)\b|deadline|act now|"
    r"immediately|urgent|asap|expires? (?:today|soon|tonight)|final notice|last chance", re.I)
OFF_PLATFORM_RE = re.compile(r"telegram|whatsapp|signal app|\bwechat\b", re.I)
FREE_EMAIL_TEXT_RE = re.compile(r"gmail|outlook\.com|hotmail|yahoo|proton", re.I)
SCAM_WORDS_RE = re.compile(r"\b(?:scam|scams|scammer|fraud|fraudulent|phishing)\b", re.I)
PRICE_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?")

HIGH_RISK = {"lookalike_domain", "scam_reports", *RISKY_PATTERNS}
MEDIUM_RISK = {"domain_mismatch", "free_email", "urgency", "off_platform_contact"}

LABELS = {
    "likely_safe": "Likely safe", "needs_verification": "Needs verification",
    "likely_suspicious": "Likely suspicious", "checks_out": "Checks out",
    "mixed": "Mixed", "red_flags": "Red flags", None: "Sourced summary",
}
PRICE_LABELS = {"fair": "fair", "above_market": "above market",
                "suspiciously_cheap": "suspiciously cheap"}


# ---------------------------------------------------------------- domain helpers
def host_of(value: str) -> str:
    """'https://www.x.com/a' -> 'x.com', 'hr@x.com' -> 'x.com'."""
    v = (value or "").strip().lower().rstrip(".,;:!?)]}'\"")
    if "@" in v and "://" not in v and "/" not in v:
        host = v.rsplit("@", 1)[1]
    else:
        if "://" not in v:
            v = "http://" + v
        try:
            host = urlparse(v).hostname or ""
        except ValueError:
            host = ""
    return host.removeprefix("www.")


def base_domain(host: str) -> str:
    """'careers.amazon.co.uk' -> 'amazon.co.uk', 'jobs.amazon.com' -> 'amazon.com'."""
    parts = [p for p in (host or "").split(".") if p]
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in {"co", "com", "org", "net", "ac", "gov", "edu"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def brand_token(company: str | None) -> str:
    """'Amazon HR' -> 'amazon', 'Bank of America' -> 'bankofamerica'."""
    words = re.findall(r"[a-z0-9]+", (company or "").lower())
    return "".join(w for w in words if w not in COMPANY_FILLER)


def normalize_variants(label: str) -> set[str]:
    """Undo common character swaps: 0->o, 1->l or i, rn->m, vv->w."""
    out = set()
    for one in ("l", "i"):
        table = str.maketrans({"0": "o", "1": one, "3": "e", "4": "a", "5": "s",
                               "7": "t", "8": "b", "$": "s", "@": "a"})
        out.add(label.translate(table).replace("rn", "m").replace("vv", "w"))
    return out


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def is_lookalike(host: str, brand: str, official_domains: list[str]) -> bool:
    bd = base_domain(host)
    if not bd or bd in official_domains:
        return False
    label = bd.split(".")[0]
    # Brand appears only after undoing swaps (amaz0n, paypa1, rnicrosoft)
    if len(brand) >= 3 and brand not in label:
        if any(brand in v for v in normalize_variants(label)):
            return True
    # Within 2 edits of an official label (amazom.com vs amazon.com)
    for off in official_domains:
        ol = off.split(".")[0]
        if len(ol) >= 5 and 0 < levenshtein(label, ol) <= 2:
            return True
    return False


def find_official_domains(results: list[dict], brand: str) -> list[str]:
    """Base domains from the 'official website' search whose name is the brand.

    Deliberately strict: if nothing matches we return [] and the verdict
    falls back to 'needs verification' instead of trusting a random site.
    """
    if not brand:
        return []
    found: list[str] = []
    for r in results:
        if "official" not in r.get("query", "").lower():
            continue
        bd = base_domain(host_of(r.get("url", "")))
        label = bd.split(".")[0].replace("-", "") if bd else ""
        if not label:
            continue
        if label == brand or (len(label) >= 4 and (brand.startswith(label) or label.startswith(brand))):
            if bd not in found:
                found.append(bd)
    return found


# ---------------------------------------------------------------- price helpers
def extract_prices(text: str) -> list[float]:
    prices = []
    for whole, cents in PRICE_RE.findall(text or ""):
        value = float(whole.replace(",", "") + ("." + cents if cents else ""))
        if 1 <= value <= 20000:
            prices.append(value)
    return prices


def parse_price(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        nums = extract_prices(value if "$" in value else "$" + value.strip())
        return nums[0] if nums else None
    return None


def first_sentence(text: str, limit: int = 140) -> str:
    s = re.split(r"(?<=[.!?])\s", (text or "").strip(), maxsplit=1)[0]
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


# ---------------------------------------------------------------- shared pieces
def _blob(r: dict) -> str:
    return f"{r.get('title', '')} {r.get('snippet', '')}".lower()


class _Collector:
    def __init__(self):
        self.flags: list[str] = []
        self.reasons: list[str] = []
        self.evidence: list[dict] = []
        self._reason_flag: dict[str, str] = {}

    def flag(self, name: str, reason: str | None = None):
        if name not in self.flags:
            self.flags.append(name)
        if reason and reason not in self.reasons:
            self.reasons.append(reason)
            self._reason_flag[reason] = name

    def sort_reasons(self, order: list[str]):
        """Most damning reasons first, so the top 3 fit on one phone screen."""
        rank = {f: i for i, f in enumerate(order)}
        self.reasons.sort(key=lambda r: rank.get(self._reason_flag.get(r, ""), len(rank)))

    def cite(self, claim: str, url: str):
        if url and not any(e["source_url"] == url and e["claim"] == claim for e in self.evidence):
            self.evidence.append({"claim": claim, "source_url": url})


def build_report(item, verdict, price_note, reasons, actions, evidence) -> str:
    lines = [f"FacetimeFriend: {LABELS.get(verdict, 'Sourced summary')}"]
    if item:
        lines.append(item[:80])
    if price_note:
        lines.append(f"Price looks {PRICE_LABELS[price_note]}")
    if reasons:
        lines += ["", "Why:"] + [f"• {r}" for r in reasons[:3]]
    if actions:
        lines += ["", "What to do:"] + [f"• {a}" for a in actions[:3]]
    urls = list(dict.fromkeys(e["source_url"] for e in evidence))[:3]
    if urls:
        lines += ["", "Sources:"] + urls
    lines += ["", "Based on live web results, not a guarantee."]
    return "\n".join(lines)


def _result(args, verdict, c: _Collector, actions, official=None, price_note=None) -> dict:
    return {
        "suggested_verdict": verdict,
        "price_note": price_note,
        "official_domain": official,
        "rule_flags": c.flags,
        "reasons": c.reasons,
        "evidence": c.evidence,
        "actions": actions,
        "report_text": build_report(args.get("item"), verdict, price_note, c.reasons, actions, c.evidence),
    }


# ---------------------------------------------------------------- scam check
def _evaluate_scam(args: dict, results: list[dict]) -> dict:
    c = _Collector()
    company = (args.get("claimed_company") or "").strip()
    brand = brand_token(company)
    official = find_official_domains(results, brand)
    official_main = official[0] if official else None

    targets = [("link", host_of(u)) for u in args.get("urls") or []]
    targets += [("email", host_of(e)) for e in args.get("emails") or []]
    targets = [(k, h) for k, h in targets if h]

    if official_main:
        src = next((r["url"] for r in results
                    if base_domain(host_of(r.get("url", ""))) == official_main), "")
        c.cite(f"{company}'s official site is {official_main}", src)

    seen_domains = set()
    for kind, host in targets:
        bd = base_domain(host)
        if bd in seen_domains:
            continue
        seen_domains.add(bd)
        if official and bd not in official:
            c.flag("domain_mismatch",
                   f"The {kind} domain {bd} does not match {company}'s official site {official_main}")
        if is_lookalike(host, brand, official):
            c.flag("lookalike_domain", f"{bd} imitates {company or official_main} by swapping characters")
        if kind == "email" and bd in FREE_EMAIL_DOMAINS and company:
            c.flag("free_email", f"{company} would not write from a free {bd} address")

    text = " ".join([*(args.get("red_flags_seen") or []), args.get("item") or ""])
    if company and FREE_EMAIL_TEXT_RE.search(text):
        c.flag("free_email", f"A company like {company} would not use a free email address")
    for name, pattern in RISKY_PATTERNS.items():
        if re.search(pattern, text, re.I):
            c.flag(name, RISKY_REASONS[name])
    if URGENCY_RE.search(text):
        c.flag("urgency", "It pressures you with a deadline")
    if OFF_PLATFORM_RE.search(text):
        c.flag("off_platform_contact", "It moves the conversation to a chat app")

    # Scam reports: a scam-query result that names the suspicious domain or phone
    suspicious = [base_domain(h) for _, h in targets
                  if base_domain(h) not in official and base_domain(h) not in FREE_EMAIL_DOMAINS]
    phones = [re.sub(r"\D", "", p)[-10:] for p in args.get("phones") or []]
    phones = [p for p in phones if len(p) == 10]
    for r in results:
        if "scam" not in r.get("query", "").lower():
            continue
        blob = _blob(r)
        if not SCAM_WORDS_RE.search(blob):
            continue
        digits = re.sub(r"\D", "", blob)
        hits = [d for d in suspicious if d in blob] + [p for p in phones if p in digits]
        for hit in hits:
            c.flag("scam_reports", f"Web results link {hit} to scam reports")
            c.cite(r.get("title") or f"Scam report mentioning {hit}", r.get("url", ""))

    c.sort_reasons(["lookalike_domain", "scam_reports", *RISKY_PATTERNS, "domain_mismatch",
                    "free_email", "urgency", "off_platform_contact"])
    flagset = set(c.flags)
    if flagset & HIGH_RISK:
        verdict = "likely_suspicious"
    elif flagset & MEDIUM_RISK:
        verdict = "needs_verification"
    elif not official:
        verdict = "needs_verification"
        c.flag("no_official_site", "Couldn't confirm the company's official website")
    elif targets:
        verdict = "likely_safe"
        c.reasons.append(f"All links and emails match the official site {official_main}")
    else:
        verdict = "needs_verification"
        c.reasons.append("There was no link or email to compare with the official site")

    go_official = f"Go to {official_main} directly instead" if official_main \
        else "Contact the company through its official website"
    if verdict == "likely_suspicious":
        actions = ["Do not click the link or reply", "Do not pay or share personal details", go_official]
    elif verdict == "needs_verification":
        actions = ["Don't click links or pay yet", go_official, "Confirm with the company before acting"]
    else:
        actions = ["Still never share passwords or login codes", go_official]
    return _result(args, verdict, c, actions, official=official_main)


# ---------------------------------------------------------------- product check
def _evaluate_product(args: dict, results: list[dict]) -> dict:
    c = _Collector()
    found = []  # (price, url)
    for r in results:
        if re.search(r"\bprice", r.get("query", ""), re.I):
            for p in extract_prices(_blob(r)):
                found.append((p, r.get("url", "")))
    prices = [p for p, _ in found]
    median = statistics.median(prices) if len(prices) >= 3 else None

    seen = parse_price(args.get("price_seen"))
    if seen is None:
        q = extract_prices(args.get("question") or "")
        seen = q[0] if q else None

    price_note = None
    if median and seen:
        ratio = seen / median
        if ratio < 0.5:
            price_note = "suspiciously_cheap"
            c.flag("suspiciously_cheap",
                   f"${seen:g} is far below the typical price of about ${median:.0f} ({len(prices)} listings)")
        elif ratio > 1.3:
            price_note = "above_market"
            c.flag("above_market", f"${seen:g} is above the typical price of about ${median:.0f}")
        else:
            price_note = "fair"
            c.reasons.append(f"${seen:g} is in line with the typical price of about ${median:.0f}")
    elif seen and not median:
        c.reasons.append("Not enough price listings found to judge the price")
    if median:
        c.cite(f"Typical price about ${median:.0f} (median of {len(prices)} listings)", found[0][1])
        for p, url in found[1:3]:
            c.cite(f"Listed at ${p:g}", url)

    if any("recall" in _blob(r) for r in results):
        c.flag("recall_mentioned", "Search results mention a recall; check the product's batch")
        rec = next(r for r in results if "recall" in _blob(r))
        c.cite(rec.get("title", "Recall mention"), rec.get("url", ""))
    if args.get("red_flags_seen"):
        c.flag("visible_red_flags", "You noticed: " + ", ".join(args["red_flags_seen"][:3]))

    tips = []
    for r in results:
        if "counterfeit" in r.get("query", "").lower() and r.get("snippet"):
            tips.append(first_sentence(r["snippet"]))
            c.cite("How to spot a counterfeit", r.get("url", ""))
        if len(tips) == 2:
            break

    if price_note == "suspiciously_cheap" or "recall_mentioned" in c.flags:
        verdict = "red_flags"
    elif price_note in (None, "above_market") or "visible_red_flags" in c.flags:
        verdict = "mixed"
    else:
        verdict = "checks_out"

    actions = [t for t in tips if t] + ["Buy from the brand or an authorized retailer"]
    return _result(args, verdict, c, actions, price_note=price_note)


# ---------------------------------------------------------------- anything else
def _evaluate_other(args: dict, results: list[dict]) -> dict:
    c = _Collector()
    for r in results[:3]:
        if r.get("snippet"):
            c.reasons.append(first_sentence(r["snippet"]))
        c.cite(r.get("title", "Source"), r.get("url", ""))
    return _result(args, None, c, [])


def evaluate(args: dict, results: list[dict]) -> dict:
    category = (args.get("category") or "other").lower()
    if category == "scam":
        return _evaluate_scam(args, results)
    if category == "product":
        return _evaluate_product(args, results)
    return _evaluate_other(args, results)


def fallback_result(args: dict, error: str = "") -> dict:
    """Returned when anything breaks, so the agent always gets a safe answer."""
    c = _Collector()
    c.reasons.append("Couldn't verify this right now")
    actions = ["Don't click links or pay", "Contact the company through its official website"]
    res = _result(args, "needs_verification", c, actions)
    res["error"] = error
    return res
