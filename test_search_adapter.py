
from keenable_search import search_for

args = {
    "category": "scam",
    "item": "Amazon job offer",
    "claimed_company": "Amazon",
    "urls": ["https://amaz0n-careers.com/onboard"],
    "emails": ["hr@amaz0n-careers.com"],
    "phones": [],
    "price_seen": None,
    "red_flags_seen": [
        "$150 equipment fee",
        "asks for SSN",
        "24-hour deadline"
    ],
    "question": "Is this job offer legit?"
}

results = search_for(args)

print("Total results:", len(results))

for result in results[:5]:
    print("Query:", result["query"])
    print("Title:", result["title"])
    print("URL:", result["url"])
    print()
