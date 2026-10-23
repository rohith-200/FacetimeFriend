
import os
import re
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from keenable import Keenable

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Verified demo company domains.
# Add other companies only after independent validation.
OFFICIAL_DOMAINS = {
    "amazon": "amazon.jobs"
}


def generate_queries(details):
    """Generate up to 3 searches from Chert arguments."""

    category = details.get("category", "other")
    item = details.get("item", "")
    company = details.get("claimed_company", "")

    if category == "scam":
        queries = []

        if company:
            queries.extend([
                f"{company} official careers website",
                f"{company} recruitment scam"
            ])

        urls = details.get("urls") or []

        if urls:
            url = urls[0]
            if "://" not in url:
                url = "https://" + url

            domain = urlparse(url).hostname

            if domain:
                queries.append(f"{domain} scam")

        return queries[:3]

    if category == "product":
        return [
            f"{item} price",
            f"{item} counterfeit how to spot",
            f"{item} reviews"
        ]

    return [item] if item else []


def search_keenable(query):
    """Run one live Keenable search."""

    client = Keenable(
        api_key=os.environ["KEENABLE_API_KEY"]
    )

    response = client.search(query)

    return {
        "query": query,
        "results": [
            {
                "title": result.title,
                "url": result.url,
                "snippet": (result.snippet or "")[:500]
            }
            for result in response.results[:5]
        ]
    }


def identify_official_domain(details, searches):
    """Identify a known official domain in search evidence."""

    company = (
        details.get("claimed_company") or ""
    ).lower().strip()

    if not company:
        return ""

    expected = OFFICIAL_DOMAINS.get(company)

    if not expected:
        return ""

    for search in searches:
        for result in search["results"]:
            hostname = (
                urlparse(result["url"]).hostname or ""
            ).lower().removeprefix("www.")

            if hostname == expected:
                return expected

    return ""


def extract_prices(searches):
    """Extract candidate dollar prices from price searches."""

    prices = []

    for search in searches:
        if "price" not in search["query"].lower():
            continue

        for result in search["results"]:
            text = result.get("snippet", "")

            matches = re.findall(
                r"\$\s*(\d+(?:\.\d{1,2})?)\b",
                text
            )

            for value in matches:
                price = float(value)

                if 1 <= price <= 10000:
                    prices.append({
                        "price": price,
                        "source_url": result["url"]
                    })

    return prices


def search_for(details):
    """
    Main Person 3 function.

    Input: structured Chert check_item arguments.
    Output: Keenable evidence for Person 2.
    """

    queries = generate_queries(details)

    if not queries:
        raise ValueError("No valid search queries generated")

    with ThreadPoolExecutor(
        max_workers=min(3, len(queries))
    ) as executor:
        searches = list(
            executor.map(search_keenable, queries)
        )

    official_domain = identify_official_domain(
        details,
        searches
    )

    prices = (
        extract_prices(searches)
        if details.get("category") == "product"
        else []
    )

    return {
        "searches": searches,
        "official_domain": official_domain,
        "prices": prices
    }
