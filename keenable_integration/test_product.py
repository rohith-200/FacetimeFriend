
import json
from verify import search_for

details = {
    "category": "product",
    "item": "Dior Sauvage Eau de Parfum 100ml",
    "claimed_company": "Dior",
    "urls": [],
    "emails": [],
    "phones": [],
    "price_seen": 39,
    "red_flags_seen": [],
    "question": "Is this real, and is $39 a good price?"
}

print("Checking perfume prices using Keenable...")

result = search_for(details)

print("\nSEARCH QUERIES:")
for search in result["searches"]:
    print("-", search["query"])

print("\nEXTRACTED PRICES:")
print(json.dumps(result["prices"], indent=2))

print("\nTOTAL PRICES:", len(result["prices"]))
