# FacetimeFriend backend: Person 2 setup (before 12:15)

## 1. Install (2 min)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Nebius credits and key (5 min)
1. Open nebius.com/promo-code; the activation code `2026-Beta-Multi-Model-hack` is pre-filled.
2. In Token Factory, open API keys, then Create API key.
3. Paste it into `.env` as `NEBIUS_API_KEY`.

## 3. Pick models (10 min)
```bash
python test_nebius.py --list
```
- Copy one model marked "likely VISION" into `NEBIUS_VISION_MODEL`.
- Copy one fast text model into `NEBIUS_TEXT_MODEL` (add `-fast` if offered).

```bash
python test_nebius.py --text      # should print JSON in a few seconds
python test_nebius.py --vision    # reads a generated fake job offer
```
Pass criteria for the vision model:
- Returns valid JSON
- Reads `amaz0n` with a zero (prints "Lookalike domain read correctly: True")
- Answers in under ~6 seconds

If it fails, try the next vision model in the list. Then test a real phone photo:
`python test_nebius.py --vision perfume.jpg`

## 4. Server and tunnel (5 min)
```bash
uvicorn server:app --port 8000 --reload
# second terminal (macOS: brew install cloudflared)
cloudflared tunnel --url http://localhost:8000
```
Open `https://<your-tunnel>.trycloudflare.com/health` on your phone: it should show `{"ok": true}`.
Share that URL with Person 1 (Chert webhooks) and Person 3 (dashboard polls `/latest`).

Endpoints (mock results for now, so teammates can build immediately):
- `POST /analyze` JSON: `image_base64` or `image_url`, plus `text`, `question`
- `POST /analyze/upload` multipart: `file`, `question` (fallback upload page, curl tests)
- `GET /latest`: pipeline state for the dashboard, including the captured frame
- `GET /health`

## 5. Data contracts
Examples live in `contracts/`. Walk Persons 1 and 3 through them at 12:15.

## 6. Voice-model fallback (only if Chert doesn't provide one)
If the LiveKit agent needs its own LLM, point LiveKit's OpenAI plugin at Nebius
(check the parameter names against the LiveKit version in the Chert starter):
```python
from livekit.plugins import openai
llm = openai.LLM(
    model=os.environ["NEBIUS_TEXT_MODEL"],
    base_url="https://api.tokenfactory.nebius.com/v1",
    api_key=os.environ["NEBIUS_API_KEY"],
)
```
Speech-to-text and text-to-speech still need providers; ask Chert what they supply.

## Done when
- [ ] `test_nebius.py --vision` passes on the fake job offer
- [ ] Tunnel URL `/health` works from a phone
- [ ] Persons 1 and 3 have the tunnel URL and the contracts
