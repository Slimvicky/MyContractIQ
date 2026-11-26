"""MyContractIQ FastAPI backend."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, EmailStr, Field, field_validator

from . import agents, audit, config, emailer
from .calendar_ics import build_ics
from .db import get_conn, init_db
from .harness import HarnessError
from .security import hash_password, new_session_token, password_problems, token_digest, verify_password

BUSINESS_TYPES = {
    "Industry": [
        "Retail & E-commerce", "Restaurant & Food Service", "Professional Services", "Healthcare & Wellness",
        "Construction & Trades", "Manufacturing", "Technology & Software", "Real Estate",
        "Education & Training", "Nonprofit", "Hospitality & Travel", "Transportation & Logistics",
        "Creative & Media", "Agriculture", "Other",
    ],
    "Operating model": [
        "B2B services", "B2C retail (storefront)", "Online / D2C", "Subscription", "Franchise",
        "Marketplace", "Wholesale / distribution", "Agency / consultancy",
    ],
}
CATEGORIES = [
    "Software / SaaS", "Telecom & Internet", "Insurance", "Utilities", "Facilities & Lease",
    "Professional Services", "Marketing", "Logistics & Shipping", "Payment Processing", "Equipment",
    "Client Services", "Staffing", "Other",
]


# ------------------------------------------------------------------ lifecycle


async def _auto_rate_checks_loop():
    """Usability improvement: the rate agent starts by itself once a contract is
    inside the 60-day renewal window, so results are waiting on the Overview page."""
    while True:
        try:
            with get_conn() as conn:
                users = [r["id"] for r in conn.execute("SELECT id FROM users")]
            for uid in users:
                await _run_due_checks(uid, trigger="auto_60_day", limit=5)
        except Exception as e:  # never let the background loop die
            audit.record("auto_rate_check_error", None, error=str(e)[:200])
        await asyncio.sleep(6 * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    audit.record("server_start", None, ai_enabled=config.ai_enabled(), model=config.OPENAI_MODEL)
    task = asyncio.create_task(_auto_rate_checks_loop())
    yield
    task.cancel()


app = FastAPI(title="MyContractIQ API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"], allow_headers=["*"],
)


# ------------------------------------------------------------------ auth


def current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Please log in.")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ?",
            (token_digest(token), datetime.now(timezone.utc).isoformat()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Your session has expired. Please log in again.")
    return dict(row)


def _public_user(u: dict) -> dict:
    return {k: u[k] for k in ("id", "first_name", "last_name", "email", "business_name", "business_type")}


def _start_session(user_id: int) -> str:
    token = new_session_token()
    expires = (datetime.now(timezone.utc) + timedelta(days=config.SESSION_DAYS)).isoformat()
    with get_conn() as conn:
        conn.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                     (token_digest(token), user_id, expires))
    return token


class RegisterIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    confirm_password: str
    business_name: str = Field(min_length=1, max_length=120)
    business_type: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@app.get("/api/health")
def health():
    return {"ok": True, "ai_enabled": config.ai_enabled(), "model": config.OPENAI_MODEL}


@app.get("/api/meta")
def meta():
    return {"business_types": BUSINESS_TYPES, "categories": CATEGORIES,
            "rate_check_window_days": config.RATE_CHECK_WINDOW_DAYS}


@app.post("/api/auth/register")
def register(body: RegisterIn):
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match.")
    problems = password_problems(body.password)
    if problems:
        raise HTTPException(400, "Password needs " + ", ".join(problems) + ".")
    all_types = {t for group in BUSINESS_TYPES.values() for t in group}
    if body.business_type not in all_types:
        raise HTTPException(400, "Please choose a business type from the list.")
    email = body.email.lower()
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "An account with this email already exists.")
        cur = conn.execute(
            "INSERT INTO users (first_name, last_name, email, business_name, business_type, password_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (body.first_name.strip(), body.last_name.strip(), email, body.business_name.strip(),
             body.business_type, hash_password(body.password)),
        )
        user_id = cur.lastrowid
        user = dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    audit.record("user_registered", user_id, email=email, business_type=body.business_type)
    email_status = emailer.send_welcome(user_id, body.first_name.strip(), body.business_name.strip(), email)
    return {"token": _start_session(user_id), "user": _public_user(user), "welcome_email": email_status}


@app.post("/api/auth/login")
def login(body: LoginIn):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (body.email.lower(),)).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        audit.record("login_failed", None, email=body.email.lower())
        raise HTTPException(401, "Email or password is incorrect.")
    audit.record("login", row["id"])
    return {"token": _start_session(row["id"]), "user": _public_user(dict(row))}


@app.post("/api/auth/logout")
def logout(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_digest(token),))
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return _public_user(user)


# ------------------------------------------------------------------ contracts


class ContractIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    counterparty: str = Field(min_length=1, max_length=160)
    line_type: Literal["expense", "revenue"]
    category: str = "Other"
    annual_value: float = Field(ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notice_days: int = Field(30, ge=0, le=365)
    auto_renew: bool = False
    owner: str = ""
    scope: str = Field("", max_length=4000)
    notes: str = Field("", max_length=4000)

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start_date")
        if v and start and v < start:
            raise ValueError("End date must be after start date")
        return v


def _latest_rate_check(conn, contract_id: int) -> Optional[dict]:
    r = conn.execute("SELECT * FROM rate_checks WHERE contract_id = ? ORDER BY id DESC LIMIT 1",
                     (contract_id,)).fetchone()
    if not r:
        return None
    return {"result": json.loads(r["result_json"]), "source": r["source"], "trigger": r["trigger"],
            "created_at": r["created_at"]}


def _enrich(c: dict, conn) -> dict:
    today = date.today()
    c = dict(c)
    c["auto_renew"] = bool(c["auto_renew"])
    c["needs_review"] = bool(c["needs_review"])
    c["has_file"] = bool(c.get("file_path"))
    c.pop("file_path", None)
    c["days_to_end"] = c["notice_deadline"] = c["days_to_notice"] = None
    c["rate_window_open"] = False
    status = "active"
    if c.get("end_date"):
        end = date.fromisoformat(c["end_date"])
        c["days_to_end"] = (end - today).days
        nd = end - timedelta(days=c["notice_days"] or 0)
        c["notice_deadline"] = nd.isoformat()
        c["days_to_notice"] = (nd - today).days
        c["rate_window_open"] = 0 <= c["days_to_end"] <= config.RATE_CHECK_WINDOW_DAYS
        if c["days_to_end"] < 0:
            status = "expired"
        elif c["days_to_notice"] <= 30 or c["days_to_end"] <= config.RATE_CHECK_WINDOW_DAYS:
            status = "action_due"
        elif c["days_to_end"] <= 90:
            status = "upcoming"
    c["status"] = status
    c["rate_check"] = _latest_rate_check(conn, c["id"])
    return c


def _get_contract(conn, user_id: int, cid: int) -> dict:
    row = conn.execute("SELECT * FROM contracts WHERE id = ? AND user_id = ?", (cid, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "Contract not found.")
    return dict(row)


def _list_contracts(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM contracts WHERE user_id = ? ORDER BY end_date IS NULL, end_date",
                            (user_id,)).fetchall()
        return [_enrich(dict(r), conn) for r in rows]


def _insert_contract(conn, user_id: int, data: dict, needs_review: bool = False) -> int:
    cur = conn.execute(
        "INSERT INTO contracts (user_id, name, counterparty, line_type, category, annual_value, start_date, "
        "end_date, notice_days, auto_renew, owner, scope, notes, needs_review) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, data["name"], data["counterparty"], data["line_type"], data.get("category") or "Other",
         data.get("annual_value") or 0, _iso(data.get("start_date")), _iso(data.get("end_date")),
         data.get("notice_days", 30), int(bool(data.get("auto_renew"))), data.get("owner", ""),
         data.get("scope", ""), data.get("notes", ""), int(needs_review)),
    )
    return cur.lastrowid


def _iso(d) -> Optional[str]:
    return d.isoformat() if isinstance(d, date) else (d or None)


@app.get("/api/contracts")
def list_contracts(user: dict = Depends(current_user)):
    return _list_contracts(user["id"])


@app.get("/api/contracts/{cid}")
def get_contract(cid: int, user: dict = Depends(current_user)):
    with get_conn() as conn:
        return _enrich(_get_contract(conn, user["id"], cid), conn)


@app.post("/api/contracts")
def create_contract(body: ContractIn, user: dict = Depends(current_user)):
    with get_conn() as conn:
        cid = _insert_contract(conn, user["id"], body.model_dump())
        out = _enrich(_get_contract(conn, user["id"], cid), conn)
    audit.record("contract_created", user["id"], contract_id=cid, name=body.name, line_type=body.line_type)
    return out


@app.put("/api/contracts/{cid}")
def update_contract(cid: int, body: ContractIn, user: dict = Depends(current_user)):
    d = body.model_dump()
    with get_conn() as conn:
        _get_contract(conn, user["id"], cid)
        conn.execute(
            "UPDATE contracts SET name=?, counterparty=?, line_type=?, category=?, annual_value=?, start_date=?, "
            "end_date=?, notice_days=?, auto_renew=?, owner=?, scope=?, notes=?, needs_review=0, "
            "updated_at=datetime('now') WHERE id=? AND user_id=?",
            (d["name"], d["counterparty"], d["line_type"], d["category"], d["annual_value"], _iso(d["start_date"]),
             _iso(d["end_date"]), d["notice_days"], int(d["auto_renew"]), d["owner"], d["scope"], d["notes"],
             cid, user["id"]),
        )
        out = _enrich(_get_contract(conn, user["id"], cid), conn)
    audit.record("contract_updated", user["id"], contract_id=cid)
    return out


@app.delete("/api/contracts/{cid}")
def delete_contract(cid: int, user: dict = Depends(current_user)):
    with get_conn() as conn:
        c = _get_contract(conn, user["id"], cid)
        conn.execute("DELETE FROM contracts WHERE id = ?", (cid,))
    if c.get("file_path"):
        (config.UPLOAD_DIR / c["file_path"]).unlink(missing_ok=True)
    audit.record("contract_deleted", user["id"], contract_id=cid, name=c["name"])
    return {"ok": True}


# ------------------------------------------------------------------ files & uploads


async def _read_pdf(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"{file.filename}: file is larger than {config.MAX_UPLOAD_MB} MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, f"{file.filename}: only PDF files are accepted.")
    return data


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:30])
    except Exception:
        return ""


def _store_file(conn, user_id: int, cid: int, data: bytes, filename: str) -> None:
    folder = config.UPLOAD_DIR / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    rel = f"{user_id}/{uuid.uuid4().hex}.pdf"
    (config.UPLOAD_DIR / rel).write_bytes(data)
    old = conn.execute("SELECT file_path FROM contracts WHERE id = ?", (cid,)).fetchone()
    if old and old["file_path"]:
        (config.UPLOAD_DIR / old["file_path"]).unlink(missing_ok=True)
    conn.execute("UPDATE contracts SET file_name = ?, file_path = ? WHERE id = ?", (filename[:200], rel, cid))


@app.post("/api/contracts/{cid}/file")
async def attach_file(cid: int, file: UploadFile = File(...), user: dict = Depends(current_user)):
    data = await _read_pdf(file)
    with get_conn() as conn:
        _get_contract(conn, user["id"], cid)
        _store_file(conn, user["id"], cid, data, file.filename or "contract.pdf")
    audit.record("file_attached", user["id"], contract_id=cid, file=file.filename)
    return {"ok": True}


@app.get("/api/contracts/{cid}/file")
def get_file(cid: int, user: dict = Depends(current_user)):
    with get_conn() as conn:
        c = _get_contract(conn, user["id"], cid)
    if not c.get("file_path"):
        raise HTTPException(404, "No PDF attached to this contract.")
    return FileResponse(config.UPLOAD_DIR / c["file_path"], media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{c["file_name"]}"'})


@app.post("/api/extract")
async def extract(file: UploadFile = File(...), user: dict = Depends(current_user)):
    """Usability improvement: read a PDF and pre-fill the contract form."""
    data = await _read_pdf(file)
    try:
        fields, source = await agents.extract_contract(_pdf_text(data), file.filename or "contract.pdf", user["id"])
    except HarnessError as e:
        raise HTTPException(502, str(e))
    return {"fields": fields.model_dump(mode="json"), "source": source}


REQUIRED_FOR_REVIEW = ("counterparty", "line_type", "annual_value", "end_date")


@app.post("/api/contracts/bulk")
async def bulk_upload(files: list[UploadFile] = File(...), user: dict = Depends(current_user)):
    """Bulk upload: many PDFs (AI reads each one) and/or CSV files (one contract per row)."""
    created, errors = [], []
    for f in files[:50]:
        name = f.filename or "file"
        try:
            if name.lower().endswith(".csv"):
                text = (await f.read()).decode("utf-8-sig")
                for i, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
                    try:
                        body = ContractIn(**{k: v for k, v in {
                            **row, "auto_renew": str(row.get("auto_renew", "")).strip().lower() in ("yes", "true", "1"),
                            "annual_value": float(str(row.get("annual_value") or 0).replace(",", "").replace("$", "")),
                            "notice_days": int(row.get("notice_days") or 30),
                            "line_type": (row.get("line_type") or "expense").strip().lower(),
                        }.items() if v not in ("", None)})
                        with get_conn() as conn:
                            cid = _insert_contract(conn, user["id"], body.model_dump())
                        created.append({"id": cid, "name": body.name, "source": f"{name} row {i}", "needs_review": False})
                    except Exception as e:
                        errors.append({"file": f"{name} row {i}", "error": str(e).split("\n")[0][:200]})
                continue
            data = await _read_pdf(f)
            fields, source = await agents.extract_contract(_pdf_text(data), name, user["id"])
            d = fields.model_dump()
            missing = [k for k in REQUIRED_FOR_REVIEW if d.get(k) in (None, "")]
            record = {
                "name": d.get("name") or name.rsplit(".", 1)[0], "counterparty": d.get("counterparty") or "Unknown",
                "line_type": d.get("line_type") or "expense", "category": d.get("category") or "Other",
                "annual_value": d.get("annual_value") or 0, "start_date": d.get("start_date"),
                "end_date": d.get("end_date"), "notice_days": d.get("notice_days") or 30,
                "auto_renew": bool(d.get("auto_renew")), "scope": d.get("scope") or "",
                "notes": f"Imported from {name} ({source})." + (f" Missing: {', '.join(missing)}." if missing else ""),
            }
            with get_conn() as conn:
                cid = _insert_contract(conn, user["id"], record, needs_review=bool(missing))
                _store_file(conn, user["id"], cid, data, name)
            created.append({"id": cid, "name": record["name"], "source": name, "needs_review": bool(missing)})
        except HTTPException as e:
            errors.append({"file": name, "error": e.detail})
        except HarnessError as e:
            errors.append({"file": name, "error": str(e)})
    audit.record("bulk_upload", user["id"], created=len(created), errors=len(errors))
    return {"created": created, "errors": errors}


@app.get("/api/templates/contracts.csv")
def csv_template():
    rows = ("name,counterparty,line_type,category,annual_value,start_date,end_date,notice_days,auto_renew,owner,scope\n"
            "Office internet,Comcast Business,expense,Telecom & Internet,2400,2026-01-01,2027-01-01,30,yes,Ops,500 Mbps fiber\n"
            "Bookkeeping retainer,Acme Dental,revenue,Client Services,18000,2026-03-01,2027-02-28,60,no,Owner,Monthly bookkeeping\n")
    return Response(rows, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="mycontractiq_template.csv"'})


@app.post("/api/contracts/sample")
def load_sample(user: dict = Depends(current_user)):
    t = date.today()
    d = lambda days: (t + timedelta(days=days)).isoformat()  # noqa: E731
    samples = [
        ("Business internet", "Comcast Business", "expense", "Telecom & Internet", 3600, d(-300), d(45), 30, True,
         "500 Mbps internet for the office"),
        ("Mobile phone plan", "Verizon", "expense", "Telecom & Internet", 4800, d(-200), d(160), 30, True,
         "6 business phone lines with data"),
        ("Accounting software", "QuickBooks Online", "expense", "Software / SaaS", 1080, d(-330), d(25), 0, True,
         "Bookkeeping, invoicing and payroll reporting"),
        ("Invoicing & payments app", "FreshBooks", "expense", "Software / SaaS", 660, d(-100), d(260), 0, True,
         "Invoicing, client payments and expense tracking"),
        ("General liability insurance", "The Hartford", "expense", "Insurance", 2900, d(-310), d(55), 30, True,
         "General liability and property coverage"),
        ("Office lease", "Main Street Properties", "expense", "Facilities & Lease", 30000, d(-700), d(400), 90, False,
         "1,200 sq ft office space"),
        ("Card processing", "Square", "expense", "Payment Processing", 5200, d(-400), d(12), 30, True,
         "Card processing for storefront and online payments"),
        ("Client service agreement – Riverside Dental", "Riverside Dental", "revenue", "Client Services", 24000,
         d(-320), d(40), 60, False, "Monthly bookkeeping and payroll services"),
        ("Client service agreement – Bloom Florist", "Bloom Florist", "revenue", "Client Services", 9600,
         d(-60), d(300), 30, True, "Quarterly tax prep and bookkeeping"),
    ]
    with get_conn() as conn:
        for (n, cp, lt, cat, v, s, e, nd, ar, sc) in samples:
            _insert_contract(conn, user["id"], {"name": n, "counterparty": cp, "line_type": lt, "category": cat,
                                                "annual_value": v, "start_date": s, "end_date": e, "notice_days": nd,
                                                "auto_renew": ar, "scope": sc, "owner": user["first_name"]})
    audit.record("sample_data_loaded", user["id"], count=len(samples))
    return {"created": len(samples)}


# ------------------------------------------------------------------ rate agent


def _fresh(check: Optional[dict]) -> bool:
    if not check:
        return False
    created = datetime.fromisoformat(check["created_at"]).replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created < timedelta(hours=config.RATE_CHECK_CACHE_HOURS)


async def _rate_check(user: dict, cid: int, trigger: str, force: bool = False) -> dict:
    with get_conn() as conn:
        c = _get_contract(conn, user["id"], cid)
        cached = _latest_rate_check(conn, cid)
    if not force and _fresh(cached) and (cached["source"] != "heuristic" or not config.ai_enabled()):
        return {**cached, "cached": True}
    result, source = await agents.check_rates(c, user["business_type"], user["id"], trigger)
    with get_conn() as conn:
        conn.execute("INSERT INTO rate_checks (contract_id, user_id, result_json, source, trigger) VALUES (?,?,?,?,?)",
                     (cid, user["id"], json.dumps(result), source, trigger))
        latest = _latest_rate_check(conn, cid)
    audit.record("rate_check", user["id"], contract_id=cid, source=source, trigger=trigger,
                 recommendation=result.get("recommendation"), impact=result.get("estimated_annual_impact"))
    return {**latest, "cached": False}


@app.post("/api/contracts/{cid}/rate-check")
async def rate_check(cid: int, force: bool = False, user: dict = Depends(current_user)):
    try:
        return await _rate_check(user, cid, "user", force)
    except HarnessError as e:
        raise HTTPException(502, str(e))


async def _run_due_checks(user_id: int, trigger: str, limit: int = 10) -> dict:
    with get_conn() as conn:
        user = dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    due = [c for c in _list_contracts(user_id) if c["rate_window_open"] and not _fresh(c["rate_check"])][:limit]
    sem = asyncio.Semaphore(3)
    done, failed = [], []

    async def one(c):
        async with sem:
            try:
                await _rate_check(user, c["id"], trigger)
                done.append(c["id"])
            except HarnessError as e:
                failed.append({"id": c["id"], "name": c["name"], "error": str(e)})

    await asyncio.gather(*(one(c) for c in due))
    return {"checked": done, "failed": failed}


@app.post("/api/rate-checks/run-due")
async def run_due(user: dict = Depends(current_user)):
    return await _run_due_checks(user["id"], trigger="overview_button")


# ------------------------------------------------------------------ overview


PRIORITY = {"high": 0, "medium": 1, "low": 2}


def _actions(contracts: list[dict]) -> list[dict]:
    acts = []
    for c in contracts:
        base = {"contract_id": c["id"], "contract_name": c["name"], "counterparty": c["counterparty"],
                "line_type": c["line_type"], "annual_value": c["annual_value"]}
        dte, dtn = c["days_to_end"], c["days_to_notice"]
        if dte is not None and dte < 0:
            acts.append({**base, "type": "expired", "priority": "high", "due_date": c["end_date"],
                         "title": "Contract has expired", "detail": "Renew, replace or archive this contract."})
        elif dtn is not None and 0 <= dtn <= 30:
            verb = "renew or raise price" if c["line_type"] == "revenue" else "renegotiate, switch or cancel"
            acts.append({**base, "type": "notice_deadline", "priority": "high" if dtn <= 14 else "medium",
                         "due_date": c["notice_deadline"], "title": f"Notice deadline in {dtn} days",
                         "detail": f"Decide whether to {verb} before the notice window closes."})
        elif dtn is not None and dtn < 0 <= dte:
            acts.append({**base, "type": "notice_passed", "priority": "medium", "due_date": c["end_date"],
                         "title": "Notice window passed" + (" – will auto-renew" if c["auto_renew"] else ""),
                         "detail": f"Contract ends in {dte} days."})
        if c["rate_window_open"] and not c["rate_check"]:
            acts.append({**base, "type": "rate_check", "priority": "medium", "due_date": c["end_date"],
                         "title": "Rate check available",
                         "detail": f"Renewal in {dte} days – the rate agent can search for better rates."})
        rc = c["rate_check"]
        if rc and dte is not None and dte >= 0 and rc["result"]["recommendation"] in ("switch", "renegotiate", "raise_price"):
            r = rc["result"]
            label = {"switch": "Switch provider", "renegotiate": "Renegotiate", "raise_price": "Raise price"}[r["recommendation"]]
            acts.append({**base, "type": "recommendation", "priority": "high" if r["estimated_annual_impact"] > 1000 else "medium",
                         "due_date": c["notice_deadline"] if dtn is not None and dtn >= 0 else c["end_date"], "title": f"{label}: ~${r['estimated_annual_impact']:,.0f}/yr",
                         "detail": r["summary"]})
        if c["needs_review"]:
            acts.append({**base, "type": "review", "priority": "low", "due_date": None,
                         "title": "Complete missing details", "detail": "Some fields could not be read from the PDF."})
    return sorted(acts, key=lambda a: (PRIORITY[a["priority"]], a["due_date"] or "9999"))


@app.get("/api/overview")
def overview(user: dict = Depends(current_user)):
    cs = _list_contracts(user["id"])
    live = [c for c in cs if c["status"] != "expired"]
    exp = [c for c in live if c["line_type"] == "expense"]
    rev = [c for c in live if c["line_type"] == "revenue"]

    def within(n):
        return len([c for c in live if c["days_to_end"] is not None and c["days_to_end"] <= n])

    recs = []
    for c in cs:
        if c["rate_check"]:
            r = c["rate_check"]["result"]
            recs.append({"contract_id": c["id"], "contract_name": c["name"], "counterparty": c["counterparty"],
                         "line_type": c["line_type"], "annual_value": c["annual_value"], "days_to_end": c["days_to_end"],
                         "source": c["rate_check"]["source"], "checked_at": c["rate_check"]["created_at"], **r})
    recs.sort(key=lambda r: -r["estimated_annual_impact"])
    eligible = [{"id": c["id"], "name": c["name"], "days_to_end": c["days_to_end"], "has_check": bool(c["rate_check"])}
                for c in cs if c["rate_window_open"]]
    by_cat: dict[str, float] = {}
    for c in exp:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + c["annual_value"]
    return {
        "metrics": {
            "total_contracts": len(cs), "active_contracts": len(live),
            "expense_contracts": len(exp), "revenue_contracts": len(rev),
            "annual_expense": sum(c["annual_value"] for c in exp),
            "annual_revenue": sum(c["annual_value"] for c in rev),
            "expiring_30": within(30), "expiring_60": within(60), "expiring_90": within(90),
            "expired": len(cs) - len(live), "auto_renewing": len([c for c in live if c["auto_renew"]]),
            "potential_savings": sum(r["estimated_annual_impact"] for r in recs if r["line_type"] == "expense"),
            "potential_uplift": sum(r["estimated_annual_impact"] for r in recs if r["line_type"] == "revenue"),
        },
        "actions": _actions(cs),
        "recommendations": recs,
        "rate_check_eligible": eligible,
        "spend_by_category": sorted(([k, v] for k, v in by_cat.items()), key=lambda x: -x[1]),
        "ai_enabled": config.ai_enabled(),
    }


# ------------------------------------------------------------------ portfolio review


@app.post("/api/portfolio/review")
async def portfolio_review(user: dict = Depends(current_user)):
    cs = [c for c in _list_contracts(user["id"]) if c["status"] != "expired"]
    if len(cs) < 2:
        raise HTTPException(400, "Add at least two active contracts to run a portfolio review.")
    try:
        result, source = await agents.review_portfolio(cs, user["business_type"], user["id"])
    except HarnessError as e:
        raise HTTPException(502, str(e))
    with get_conn() as conn:
        conn.execute("INSERT INTO portfolio_reviews (user_id, result_json, source) VALUES (?,?,?)",
                     (user["id"], json.dumps(result), source))
    audit.record("portfolio_review", user["id"], source=source, findings=len(result["findings"]),
                 savings=result["total_estimated_savings"])
    return {"result": result, "source": source, "created_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/portfolio/latest")
def portfolio_latest(user: dict = Depends(current_user)):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM portfolio_reviews WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                         (user["id"],)).fetchone()
    if not r:
        return None
    return {"result": json.loads(r["result_json"]), "source": r["source"], "created_at": r["created_at"]}


# ------------------------------------------------------------------ calendar & audit


@app.get("/api/calendar.ics")
def calendar_all(user: dict = Depends(current_user)):
    cs = _list_contracts(user["id"])
    audit.record("calendar_export", user["id"], contracts=len(cs))
    return Response(build_ics(cs), media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="mycontractiq_dates.ics"'})


@app.get("/api/contracts/{cid}/calendar.ics")
def calendar_one(cid: int, user: dict = Depends(current_user)):
    with get_conn() as conn:
        c = _enrich(_get_contract(conn, user["id"], cid), conn)
    audit.record("calendar_export", user["id"], contract_id=cid)
    return Response(build_ics([c]), media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="contract_{cid}.ics"'})


@app.get("/api/audit/verify")
def audit_verify(user: dict = Depends(current_user)):
    return audit.verify_chain()


# ------------------------------------------------------------------ serve built frontend

FRONTEND_DIST = config.ROOT_DIR / "frontend" / "dist"

if FRONTEND_DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (FRONTEND_DIST / path).resolve()
        if path and file.is_file() and FRONTEND_DIST.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
