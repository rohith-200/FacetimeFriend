import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from fastapi.testclient import TestClient
from rules import evaluate, is_lookalike
from search import mock_search
from parser import message_to_args
from main import app

C = pathlib.Path(__file__).parent.parent / "contracts"
JOB = json.loads((C / "check_item_args.json").read_text())
PERFUME = json.loads((C / "check_item_args_product.json").read_text())


def test_fake_job_offer_is_likely_suspicious():
    r = evaluate(JOB, mock_search(JOB))
    assert r["suggested_verdict"] == "likely_suspicious"
    assert r["official_domain"] == "amazon.jobs"
    for f in ["domain_mismatch", "lookalike_domain", "upfront_fee", "asks_for_ssn", "urgency", "scam_reports"]:
        assert f in r["rule_flags"], f
    assert r["reasons"][0].startswith("amaz0n-careers.com imitates")
    assert any("amazon.jobs" in x for x in r["reasons"])


def test_official_link_is_likely_safe():
    args = {**JOB, "urls": ["https://www.amazon.jobs/en/jobs/123"], "emails": [], "red_flags_seen": [],
            "item": "Job posting"}
    assert evaluate(args, mock_search(args))["suggested_verdict"] == "likely_safe"


def test_no_official_site_needs_verification():
    args = {"category": "scam", "claimed_company": "Acme", "urls": ["https://acme.com"]}
    assert evaluate(args, [])["suggested_verdict"] == "needs_verification"


def test_free_email_needs_verification():
    args = {**JOB, "urls": [], "emails": ["amazonhr@gmail.com"], "red_flags_seen": [], "item": "Email"}
    r = evaluate(args, mock_search(args))
    assert r["suggested_verdict"] == "needs_verification"
    assert "free_email" in r["rule_flags"]


def test_lookalikes():
    assert is_lookalike("paypa1.com", "paypal", ["paypal.com"])
    assert is_lookalike("rnicrosoft.com", "microsoft", ["microsoft.com"])
    assert is_lookalike("amazom.com", "amazon", ["amazon.com"])
    assert not is_lookalike("paypal.com", "paypal", ["paypal.com"])


def test_cheap_perfume_has_red_flags():
    r = evaluate(PERFUME, mock_search(PERFUME))
    assert r["price_note"] == "suspiciously_cheap"
    assert r["suggested_verdict"] == "red_flags"
    assert any("batch code" in a for a in r["actions"])


def test_fair_perfume_checks_out():
    args = {**PERFUME, "price_seen": "$150"}
    r = evaluate(args, mock_search(args))
    assert (r["price_note"], r["suggested_verdict"]) == ("fair", "checks_out")


def test_texted_message_parser():
    a = message_to_args("Hi from Amazon HR! Onboard at https://amaz0n-careers.com/onboard. "
                        "Pay the $150 fee within 24 hours. Email hr@amaz0n-careers.com or call (555) 123-4567.")
    assert a["urls"] == ["https://amaz0n-careers.com/onboard"]
    assert a["emails"] == ["hr@amaz0n-careers.com"]
    assert a["claimed_company"] == "Amazon"
    assert len(a["phones"]) == 1
    assert evaluate(a, mock_search(a))["suggested_verdict"] == "likely_suspicious"


def test_api_end_to_end():
    client = TestClient(app)
    r = client.post("/verify", json={**JOB, "category": "Scam", "urls": "https://amaz0n-careers.com/onboard"})
    assert r.status_code == 200 and r.json()["suggested_verdict"] == "likely_suspicious"
    latest = client.get("/latest").json()
    assert latest["status"] == "done" and latest["steps"][-1]["step"] == "verdict"
