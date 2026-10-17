"""Credentials. PRD §5 FR-AUTH-06: Argon2id password hashing, server-side sessions, password reset, admin MFA;
§10/§11: per-app API keys with rate limits.

IMPLEMENTATION NECESSITIES (not in the PRD, listed in docs/PRD_GAPS.md §4): argon2-cffi defaults for Argon2id, 32-byte random
session and one-time tokens stored only as SHA-256 hashes, TOTP (RFC 6238, pyotp) for admin MFA with the secret encrypted by
Fernet (cryptography), SHA-256 hashed API keys, in-memory rate-limit windows."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque
from typing import Optional
from uuid import UUID

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

# ---- passwords: Argon2id (PRD §5 FR-AUTH-06 "Argon2id preferred"); older scrypt hashes still verify and are upgraded -----
_ARGON = PasswordHasher()                 # argon2-cffi defaults (Argon2id, RFC 9106 low-memory profile)
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    return _ARGON.hash(password)


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("$argon2"):
        try:
            return _ARGON.verify(stored, password)
        except (VerificationError, InvalidHashError):
            return False
    try:                                   # legacy scrypt$N$r$p$salt$hash (before 2026-10-17)
        _, n, r, p, salt, dk = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


def needs_rehash(stored: str) -> bool:
    """True for legacy scrypt hashes and for Argon2 hashes made with weaker parameters: rehash after a successful login."""
    if not stored.startswith("$argon2"):
        return True
    try:
        return _ARGON.check_needs_rehash(stored)
    except InvalidHashError:
        return True


# PRD §5 FR-AUTH-01 asks for a "password policy" without rules; this is the minimum (docs/PRD_GAPS.md §3).
PASSWORD_MIN_LENGTH = 8


def password_problem(password: str, *personal: str) -> Optional[str]:
    """A short reason the password is not acceptable, or None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Use at least {PASSWORD_MIN_LENGTH} characters."
    low = password.lower()
    for p in personal:
        if p and len(p) >= 3 and p.lower() in low:
            return "Do not use your name, username or email in the password."
    if len(set(password)) < 4:
        return "Choose a less repetitive password."
    return None


# ---- opaque tokens: sessions and one-time links (only the SHA-256 hash is stored) ---------------------------------------
def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---- admin MFA: TOTP (RFC 6238), secret encrypted at rest (PRD §10) -----------------------------------------------------
def _fernet(key: str) -> Fernet:
    # Any secret string is accepted; it is stretched to a valid 32-byte Fernet key.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def encrypt_secret(plain: str, key: str) -> str:
    return _fernet(key).encrypt(plain.encode()).decode()


def decrypt_secret(token: str, key: str) -> Optional[str]:
    try:
        return _fernet(key).decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, account: str, issuer: str = "Quixotic AI") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    code = re.sub(r"\s", "", code or "")
    return bool(re.fullmatch(r"\d{6}", code)) and pyotp.TOTP(secret).verify(code, valid_window=1)


# ---- signed short-lived tokens (HS256); used for service-to-service calls, never as a user login --------------------
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
