"""Welcome email. Sends via SMTP when configured in .env, otherwise saves the
email to output/outbox/ so it can be inspected locally."""
from __future__ import annotations

import smtplib
from datetime import datetime
from email.message import EmailMessage

from . import audit, config


def _welcome(first_name: str, business_name: str, to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Welcome to MyContractIQ, {business_name}!"
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg.set_content(
        f"""Hi {first_name},

Welcome to MyContractIQ — and thank you for choosing us to support {business_name.rstrip('.')}.

We built MyContractIQ for small businesses like yours: one place to keep every contract,
never miss a renewal date, and find savings you would otherwise leave on the table.

Here's how to get started:
  1. Upload your contracts (one at a time or in bulk) on the Upload Contracts page.
  2. Check the Overview page for actions due and renewal reminders.
  3. Run a Portfolio Review to spot overlapping or redundant contracts.
  4. Export key dates straight to your calendar.

From 60 days before each renewal, our rate agent can search the web for better rates for you.

Here's to spending less time on paperwork and more time growing your business.

The MyContractIQ Team
"""
    )
    return msg


def send_welcome(user_id: int, first_name: str, business_name: str, to: str) -> str:
    msg = _welcome(first_name, business_name, to)
    if config.SMTP_HOST:
        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
                s.starttls()
                if config.SMTP_USER:
                    s.login(config.SMTP_USER, config.SMTP_PASSWORD)
                s.send_message(msg)
            audit.record("welcome_email", user_id, delivery="smtp", to=to)
            return "sent"
        except Exception as e:
            audit.record("welcome_email", user_id, delivery="smtp_failed", to=to, error=str(e)[:200])
    path = config.OUTBOX_DIR / f"welcome_{user_id}_{datetime.now():%Y%m%d%H%M%S}.eml"
    path.write_bytes(bytes(msg))
    audit.record("welcome_email", user_id, delivery="outbox", file=path.name)
    return "saved_to_outbox"
