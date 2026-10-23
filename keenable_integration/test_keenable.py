
import os
from pathlib import Path
from dotenv import load_dotenv
from keenable import Keenable

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

api_key = os.getenv("KEENABLE_API_KEY")

if not api_key:
    raise RuntimeError("Keenable API key not found!")

client = Keenable(api_key=api_key)

print("Connecting to Keenable...")
print("Searching Amazon official careers website...")

response = client.search(
    "Amazon official careers website"
)

print("Search response:")
print(response)
