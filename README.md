# FacetimeFriend backend (Person 2)

    pip install -r requirements.txt
    uvicorn main:app --port 8000 --reload
    cloudflared tunnel --url http://localhost:8000     # share the https URL
    python -m pytest -q tests                          # run before every push

Endpoints: GET /health · POST /verify (check_item args) · POST /verify_text ({"text": ...}) · GET /latest

USE_MOCK=1 (default) uses fake search results. When Person 3's keenable_search.py
is in this folder: USE_MOCK=0 uvicorn main:app --port 8000
Live results are cached to cache/search_cache.json and used if Keenable is slow.

Files: main.py (API + /latest state) · rules.py (all rules, verdict, report text)
search.py (queries, mock, Keenable swap, cache) · parser.py (texted messages) · contracts/
