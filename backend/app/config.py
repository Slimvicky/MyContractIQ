"""Central configuration. Reads the .env file in the project root folder."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"

load_dotenv(ROOT_DIR / ".env")

# Where data is stored. By default it lives inside the project. On a host with a temporary
# filesystem (e.g. Render), set DATA_DIR to a persistent disk mount such as /var/data;
# the audit trail and outbox then go to DATA_DIR/output unless OUTPUT_DIR is also set.
_data_env = os.getenv("DATA_DIR", "").strip()
_output_env = os.getenv("OUTPUT_DIR", "").strip()
DATA_DIR = Path(_data_env).expanduser() if _data_env else BACKEND_DIR / "data"
OUTPUT_DIR = (Path(_output_env).expanduser() if _output_env
              else DATA_DIR / "output" if _data_env else ROOT_DIR / "output")
UPLOAD_DIR = DATA_DIR / "uploads"
EXTERNAL_STORAGE = bool(_data_env)  # True when DATA_DIR points outside the app folder
DB_PATH = DATA_DIR / "mycontractiq.db"
AUDIT_TRAIL_PATH = OUTPUT_DIR / "audit_trail.json"
OUTBOX_DIR = OUTPUT_DIR / "outbox"
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

# Spending guards (override in .env)
DAILY_AGENT_RUNS_PER_USER = int(os.getenv("DAILY_AGENT_RUNS_PER_USER", "80"))
DAILY_TOKENS_PER_USER = int(os.getenv("DAILY_TOKENS_PER_USER", "600000"))
DAILY_TOKENS_GLOBAL = int(os.getenv("DAILY_TOKENS_GLOBAL", "10000000"))
RUN_REQUEST_LIMIT = int(os.getenv("RUN_REQUEST_LIMIT", "10"))        # model round-trips per run (stops loops)
RUN_TOKEN_LIMIT = int(os.getenv("RUN_TOKEN_LIMIT", "150000"))        # tokens per run

# Prices, USD (gpt-6-luna list price, Nov 2026)
PRICE_INPUT_PER_M = float(os.getenv("PRICE_INPUT_PER_M", "0.10"))
PRICE_CACHED_INPUT_PER_M = float(os.getenv("PRICE_CACHED_INPUT_PER_M", "0.01"))
PRICE_OUTPUT_PER_M = float(os.getenv("PRICE_OUTPUT_PER_M", "0.50"))
PRICE_WEB_SEARCH_CALL = float(os.getenv("PRICE_WEB_SEARCH_CALL", "0.01"))  # $10 per 1,000 calls

for d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, OUTBOX_DIR):
    d.mkdir(parents=True, exist_ok=True)


def ai_enabled() -> bool:
    return bool(OPENAI_API_KEY) and not OPENAI_API_KEY.startswith("sk-your")
