"""Central configuration. Reads the .env file in the project root folder."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
DATA_DIR = BACKEND_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "mycontractiq.db"
OUTPUT_DIR = ROOT_DIR / "output"
AUDIT_TRAIL_PATH = OUTPUT_DIR / "audit_trail.json"
OUTBOX_DIR = OUTPUT_DIR / "outbox"

load_dotenv(ROOT_DIR / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna").strip() or "gpt-6-luna"

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", "MyContractIQ <no-reply@mycontractiq.app>").strip()

# Business rules
RATE_CHECK_WINDOW_DAYS = 60      # agent may start a rate search this many days before renewal
RATE_CHECK_CACHE_HOURS = 24      # re-use a rate search result for this long
SESSION_DAYS = 7
MAX_UPLOAD_MB = 15

for d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, OUTBOX_DIR):
    d.mkdir(parents=True, exist_ok=True)


def ai_enabled() -> bool:
    return bool(OPENAI_API_KEY) and not OPENAI_API_KEY.startswith("sk-your")
