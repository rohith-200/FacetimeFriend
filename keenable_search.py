
"""
Adapter connecting the working Keenable module
to Person 2's search.py contract.
"""

from keenable_integration.verify import search_keenable
from search import build_queries


def search_for(args: dict) -> list[dict]:
    """
    Return flat search results expected by search.py.

    Each item contains:
    query, title, url, snippet
    """

    queries = build_queries(args)

    if not queries:
        return []

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(
        max_workers=min(3, len(queries))
    ) as executor:
        grouped_results = list(
            executor.map(search_keenable, queries)
        )

    flat_results = []

    for group in grouped_results:
        query = group["query"]

        for result in group["results"]:
            flat_results.append({
                "query": query,
                "title": result["title"],
                "url": result["url"],
                "snippet": result["snippet"]
            })

    return flat_results
