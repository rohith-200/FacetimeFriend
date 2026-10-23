
from urllib.parse import urlparse
from difflib import SequenceMatcher

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com",
    "outlook.com", "hotmail.com"
}

RISKY_TERMS = {
    "upfront fee": ["equipment fee", "upfront fee", "registration fee"],
    "SSN": ["ssn", "social security number"],
    "bank details": ["bank details", "bank account"],
    "gift cards": ["gift card"],
    "crypto": ["cryptocurrency", "bitcoin", "crypto"]
}

def extract_domain(value):
    value = value.strip().lower()
    if "@" in value and "://" not in value:
        return value.rsplit("@", 1)[-1]
    if "://" not in value:
        value = "https://" + value
    return (urlparse(value).hostname or "").removeprefix("www.")

def check_scam_rules(understanding, official_domain):
    details = understanding.get("visible_details", {})
    emails = details.get("emails", [])
    urls = details.get("urls", [])

    domains = [
        extract_domain(value)
        for value in emails + urls
    ]
    domains = [d for d in domains if d]

    official_domain = extract_domain(official_domain)

    mismatch = bool(
        official_domain and domains
        and any(
            d != official_domain
            and not d.endswith("." + official_domain)
            for d in domains
        )
    )

    def looks_similar(domain):
        if not official_domain:
            return False

        official_brand = official_domain.split(".")[0]

        normalized = (
            domain.lower()
            .replace("0", "o")
            .replace("1", "l")
        )

        domain_brand = normalized.split(".")[0].split("-")[0]

        similarity = SequenceMatcher(
            None,
            domain_brand,
            official_brand
        ).ratio()

        return (
            domain != official_domain
            and similarity >= 0.8
        )


    lookalike = bool(
        official_domain
        and any(looks_similar(d) for d in domains)
    )

    free_email = any(
        extract_domain(email) in FREE_EMAIL_DOMAINS
        for email in emails
    )

    message = " ".join([
        str(details.get("label_text", "")),
        str(details.get("price", "")),
        understanding.get("item", "")
    ]).lower()

    risky_requests = [
        label
        for label, terms in RISKY_TERMS.items()
        if any(term in message for term in terms)
    ]

    return {
        "domain_mismatch": mismatch,
        "lookalike": lookalike,
        "free_email": free_email,
        "risky_requests": risky_requests
    }
