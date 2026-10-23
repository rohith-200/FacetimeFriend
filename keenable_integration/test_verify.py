

import json

from verify import search_for

details = {
    "category": "scam",
    "item": "Job offer text from Amazon HR",
    "claimed_company": "Amazon",
    "urls": [
        "https://amaz0n-careers.com/onboard"
    ],
    "emails": [
        "hr@amaz0n-careers.com"
    ],
    "phones": [],
    "price_seen": None,
    "red_flags_seen": [
        "$150 equipment fee",
        "asks for SSN",
        "24-hour deadline"
    ],
    "question": "Is this job offer legit?"
}

print("Running new Chert + Keenable verification...")

result = search_for(details)

print(json.dumps(result, indent=2))
