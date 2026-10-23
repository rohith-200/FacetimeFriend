"""
Nebius setup check for FacetimeFriend (Person 2).

Usage:
  python test_nebius.py --list              # list available models, flag likely vision ones
  python test_nebius.py --text              # test the text model (NEBIUS_TEXT_MODEL)
  python test_nebius.py --vision            # test the vision model on a generated fake job offer
  python test_nebius.py --vision photo.jpg  # test the vision model on your own photo
"""
import base64
import io
import json
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageDraw

load_dotenv()

client = OpenAI(
    base_url=os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1"),
    api_key=os.environ["NEBIUS_API_KEY"],
)

VISION_HINTS = ("vl", "vision", "llava", "pixtral", "gemma-3", "llama-4", "qwen2.5-vl", "qwen3-vl")


def list_models():
    models = sorted(m.id for m in client.models.list().data)
    print(f"{len(models)} models available:\n")
    for m in models:
        tag = "  <- likely VISION" if any(h in m.lower() for h in VISION_HINTS) else ""
        print(f"  {m}{tag}")
    print("\nPut one vision model in NEBIUS_VISION_MODEL and one fast text model in NEBIUS_TEXT_MODEL.")
    print("Tip: append -fast to a model ID if the catalog offers the fast flavor.")


def test_text():
    model = os.environ["NEBIUS_TEXT_MODEL"]
    t = time.time()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": 'Return JSON only: {"status": "ok", "model": "<your name>"}'}],
        temperature=0,
    )
    print(f"[text] {model} answered in {time.time() - t:.1f}s:")
    print(resp.choices[0].message.content)


def fake_job_offer_image() -> bytes:
    """Draws a fake job-offer text so we can test reading a lookalike domain."""
    img = Image.new("RGB", (1000, 420), "white")
    d = ImageDraw.Draw(img)
    lines = [
        "From: hr@amaz0n-careers.com",
        "Congratulations! You are hired as Remote Data Assistant.",
        "Pay $150 equipment fee today to start.",
        "Send your SSN and bank details within 24 hours.",
        "Apply: https://amaz0n-careers.com/onboard",
    ]
    for i, line in enumerate(lines):
        d.text((30, 30 + i * 70), line, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def load_image(path: str) -> bytes:
    img = Image.open(path).convert("RGB")
    img.thumbnail((1024, 1024))  # keep requests small and fast
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_vision(path: str | None):
    model = os.environ["NEBIUS_VISION_MODEL"]
    image = load_image(path) if path else fake_job_offer_image()
    b64 = base64.b64encode(image).decode()
    prompt = (
        "Identify what is shown. Return JSON only with keys: category (scam|product|document|other), "
        "item, visible_details {sender, emails, urls, phones, label_text, price}, user_intent. "
        "Copy emails and URLs character by character, including digits that look like letters. "
        "User question: Is this legit?"
    )
    t = time.time()
    resp = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    print(f"[vision] {model} answered in {time.time() - t:.1f}s:")
    print(raw)
    cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
        print("\nValid JSON.")
        if not path:
            emails = json.dumps(data.get("visible_details", {}))
            ok = "amaz0n" in emails
            print("Lookalike domain read correctly (amaz0n with a zero):", ok)
    except json.JSONDecodeError:
        print("\nNOT valid JSON: tighten the prompt or try another model.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--list":
        list_models()
    elif args[0] == "--text":
        test_text()
    elif args[0] == "--vision":
        test_vision(args[1] if len(args) > 1 else None)
    else:
        print(__doc__)
