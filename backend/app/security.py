"""Password hashing (salted scrypt) and session tokens.

Passwords are never stored. We store `scrypt$N$r$p$<salt>$<hash>` where the salt is
16 random bytes unique to each user. scrypt is deliberately slow and memory-hard,
which makes brute-forcing a stolen database very expensive.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

N, R, P, DKLEN = 2**14, 8, 1, 64


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=DKLEN)
    return "scrypt${}${}${}${}${}".format(
        N, R, P, base64.b64encode(salt).decode(), base64.b64encode(dk).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.scrypt(password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


def password_problems(password: str) -> list[str]:
    problems = []
    if len(password) < 8:
        problems.append("at least 8 characters")
    if not re.search(r"[A-Za-z]", password):
        problems.append("a letter")
    if not re.search(r"\d", password):
        problems.append("a number")
    return problems


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    """Only a SHA-256 digest of each session token is stored in the database."""
    return hashlib.sha256(token.encode()).hexdigest()
