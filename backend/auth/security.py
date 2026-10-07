"""Credentials. PRD §41 (V1): email or employee ID + password. §40: per-app API keys with rate limit.

IMPLEMENTATION NECESSITIES (not in the PRD, listed in docs/PRD_GAPS.md): scrypt password hashing,
HS256 JWT bearer tokens, SHA-256 hashed API keys, in-memory rate-limit window."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque
from typing import Optional
from uuid import UUID

import jwt

# ---- passwords ------------------------------------------------------------------------------
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


# ---- JWT (stack decision: "JWT / Cognito"; self-issued HS256 JWT now, Cognito can replace `read_token` later) ----
def issue_token(user_id: UUID, secret: str, ttl_seconds: int, now: Optional[float] = None) -> str:
    t = int(now or time.time())
    return jwt.encode({"sub": str(user_id), "iat": t, "exp": t + ttl_seconds}, secret, algorithm="HS256")


def read_token(token: str, secret: str, now: Optional[float] = None) -> Optional[UUID]:
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_exp": False, "require": ["sub", "exp"]})
        return UUID(claims["sub"]) if claims["exp"] > (now or time.time()) else None
    except Exception:
        return None


# ---- API keys: qx_live_<random>, like an LLM provider's keys (owner decision: no app name inside the key) ------
KEY_PREFIX = "qx_live_"


def generate_api_key() -> tuple[str, str, str, str]:
    """Returns (full_key_shown_once, prefix, sha256_hash_to_store, last4_for_display)."""
    full = KEY_PREFIX + secrets.token_urlsafe(32)
    return full, KEY_PREFIX, hash_api_key(full), full[-4:]


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ---- rate limiting (PRD §40 "Rate limit", §51) ------------------------------------------------
class SlidingWindowLimiter:
    """Per-process limiter. With several API instances a shared store would be needed (PRD silent)."""

    def __init__(self, window_seconds: int = 60) -> None:
        self._w, self._hits = window_seconds, defaultdict(deque)

    def allow(self, key: str, limit: int, now: Optional[float] = None) -> bool:
        t, q = now if now is not None else time.monotonic(), self._hits[key]
        while q and q[0] <= t - self._w:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(t)
        return True


# ---- login brute-force protection (PRD §51 lists rate limiting; thresholds are not specified: docs/PRD_GAPS.md) ----
LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW_SECONDS = 15 * 60


class LoginThrottle:
    """Blocks further attempts for an identifier after too many recent failures. Per-process, like the key limiter."""

    def __init__(self, max_failures: int = LOGIN_MAX_FAILURES, window: int = LOGIN_WINDOW_SECONDS) -> None:
        self._max, self._w, self._fails = max_failures, window, defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque:
        q = self._fails[key.lower()]
        while q and q[0] <= now - self._w:
            q.popleft()
        return q

    def blocked(self, identifier: str, now: Optional[float] = None) -> bool:
        return len(self._prune(identifier, now if now is not None else time.monotonic())) >= self._max

    def failure(self, identifier: str, now: Optional[float] = None) -> None:
        t = now if now is not None else time.monotonic()
        self._prune(identifier, t).append(t)

    def success(self, identifier: str) -> None:
        self._fails.pop(identifier.lower(), None)


_DUMMY_HASH = hash_password("not-a-real-password")   # verified when the user does not exist, so timing does not reveal accounts
