"""Builds an .ics calendar file with important contract dates (works with Google,
Outlook and Apple Calendar)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .config import RATE_CHECK_WINDOW_DAYS


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _event(uid: str, day: date, summary: str, description: str, alarm_days: int = 7) -> list[str]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return [
        "BEGIN:VEVENT",
        f"UID:{uid}@mycontractiq",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
        f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
        f"SUMMARY:{_esc(summary)}",
        f"DESCRIPTION:{_esc(description)}",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_esc(summary)}",
        f"TRIGGER:-P{alarm_days}D",
        "END:VALARM",
        "END:VEVENT",
    ]


def build_ics(contracts: list[dict]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MyContractIQ//Contracts//EN",
             "CALSCALE:GREGORIAN", "X-WR-CALNAME:MyContractIQ contract dates",
             "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H"]
    for c in contracts:
        if not c.get("end_date"):
            continue
        end = date.fromisoformat(c["end_date"])
        label = f"{c['name']} ({c['counterparty']})"
        kind = "Revenue" if c["line_type"] == "revenue" else "Expense"
        lines += _event(f"c{c['id']}-end", end, f"Contract ends: {label}",
                        f"{kind} contract, ${c['annual_value']:,.0f}/yr. Auto-renew: {'yes' if c['auto_renew'] else 'no'}.")
        notice = end - timedelta(days=int(c.get("notice_days") or 0))
        if notice != end:
            lines += _event(f"c{c['id']}-notice", notice, f"Notice deadline: {label}",
                            f"Last day to give notice ({c['notice_days']} days before end) to cancel or renegotiate.", 14)
        lines += _event(f"c{c['id']}-rate", end - timedelta(days=RATE_CHECK_WINDOW_DAYS),
                        f"Rate check window opens: {label}",
                        "MyContractIQ rate agent can now search the web for better rates.", 1)
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
