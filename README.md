# MyContractIQ

**Live app: https://mycontractiq.onrender.com** · **Report: [report/MyContractIQ_Report.html](report/MyContractIQ_Report.html)** · **Repo: https://github.com/Slimvicky/MyContractIQ**

**Contract management for small businesses.** Track every contract, get reminders before renewals and notice deadlines, and let AI agents find better rates and hidden savings.

> We empower small businesses with simple, affordable tools to manage contracts, streamline operations, and connect essential business systems—all in one platform.

Built for MGT 409 (Final Project).

## Features

| Page | What it does |
|---|---|
| **Overview** | Summary metrics (contracts, annual expense vs. revenue, renewals ≤ 60 days, identified savings), a prioritized **Actions due** list, and recommendations from the rate agent |
| **Contracts** | Full details for each contract, notice deadlines, PDF, edit/delete, per-contract rate check and calendar export |
| **Portfolio Review** | AI agent reviews all contracts together to find redundancy, consolidation and scale savings that are hidden when contracts sit in silos. Includes contracts that expired in the last 180 days if they're marked *still being paid* (or auto-renew) |
| **Upload Contracts** | Bulk upload (many PDFs and/or a CSV) or one contract at a time, with AI auto-fill from PDF |
| **Repository** | Simple row-by-row table of all contracts with a link to open each PDF |
| **About Us** | Company mission |
| **Log in / Create account** | First and last name, business name, business type (industry / operating model), email, password and confirmation |

- **Expense vs. revenue lines.** Vendor contracts (we pay) and client service agreements (we get paid) are tracked separately. For revenue lines, the rate agent checks whether you're under-pricing.
- **Rate agent (Pydantic AI + OpenAI web search).** Starts on its own 60 days before each renewal (background job) and can also be run from the Overview or Contracts page. Each check runs the agent 3 times in parallel (`RATE_CHECK_RUNS`) and shows the majority recommendation, the median estimate and the range. Confidence drops to low when the runs disagree.
- **Calendar export.** An `.ics` file with end dates, notice deadlines and the date each rate-check window opens, with reminders. Works with Google, Outlook and Apple Calendar.
- **Welcome email** sent when an account is created (via SMTP, or saved to `output/outbox/` if SMTP isn't configured).

### Security
- Passwords are **salted and hashed** with scrypt (16-byte random salt per user). Plain-text passwords are never stored.
- Session tokens are random. Only their SHA-256 digests are stored.
- **Append-only audit trail** at `output/audit_trail.json` (JSON Lines). Each entry is hash-chained to the one before it, so edits to history can be detected (`GET /api/audit/verify`). Secrets are redacted.
- **Agent harness** (`backend/app/harness.py`) wraps every agent call. It adds prompt-injection defense (untrusted PDF/scope text is scrubbed and fenced in `<untrusted_data>` tags), timeouts, retries with backoff, structured-output validation, removal of made-up contract IDs, and audit logging. It also enforces spending limits: each run is capped at 10 model calls and 150k tokens, and each business has a daily cap of 80 runs and 700k tokens, plus an app-wide 10M-token daily cap. Tokens, cached tokens, web searches and cost are recorded per run in the `agent_usage` table.

### Agent / backend usability improvements
1. **AI auto-extraction from PDFs.** Upload a contract PDF (or 50 at once) and the extraction agent fills in the vendor/client, value, dates, notice period and scope. Anything it can't read is flagged *Needs review*.
2. **Automatic, cached and fault-tolerant rate checks.** The rate agent runs on its own inside the 60-day window, results are cached for 24 h (instant page loads, no repeat API cost), and if the AI is unavailable the app falls back to a clearly labelled rule-based estimate instead of showing an error.

## Tech stack
- **Frontend:** React + Vite + TypeScript, React Router, lucide-react icons
- **Backend:** Python FastAPI, Pydantic AI (OpenAI Responses model `gpt-6-luna` + web search), SQLite, pypdf

## Running locally

Requires Python 3.10+ and Node 20+.

```bash
# 1. Configuration: copy the example and add your OpenAI key
cp .env.example .env

# 2. Backend
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# 3. Frontend build
cd frontend && npm install && npm run build && cd ..

# 4. Run (serves the API and the built frontend)
.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
```

Open http://127.0.0.1:8000. For frontend development with hot reload, run `npm run dev` in `frontend/` (it proxies `/api` to port 8000) and open http://localhost:5173.

Without an `OPENAI_API_KEY`, the app runs in offline mode: every agent uses a clearly labelled rule-based fallback.

## Deploying on Render

- **Build command:** `pip install -r backend/requirements.txt && cd frontend && npm ci && npm run build`
- **Start command:** `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`
- **Environment:** `OPENAI_API_KEY`, `OPENAI_MODEL`, `PYTHON_VERSION=3.12.8`, and `DATA_DIR=/var/data`.
- **Persistent disk (required to keep data).** Render's filesystem is temporary on every plan, so attach a disk (Service → Disks, mount path `/var/data`, 1 GB is plenty). With `DATA_DIR` set, the SQLite database, uploaded PDFs, audit trail and outbox are all stored on the disk and survive redeploys. `GET /api/health` returns `"external_storage": true` when this is active.

## Project structure

```
backend/app/
  main.py          FastAPI routes (auth, contracts, uploads, overview, agents, calendar)
  agents.py        Rate, portfolio and extraction agents (Pydantic AI) + fallbacks
  harness.py       Agent harness: injection defense, retries, timeouts, spending caps, usage ledger, auditing
  security.py      scrypt password hashing, session tokens
  audit.py         Append-only, hash-chained audit trail
  calendar_ics.py  .ics export
  emailer.py       Welcome email
frontend/src/
  pages/           Overview, Contracts, Portfolio, Upload, Repository, AboutUs, Login
  components/      NavBar, ContractForm, UI primitives
output/            audit_trail.json and email outbox (git-ignored)
```
