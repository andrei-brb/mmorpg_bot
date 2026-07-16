"""Password hashing — stdlib scrypt, no new dependency.

`hashlib.scrypt` (RFC 7914) is memory-hard: unlike a plain SHA, it costs an
attacker real RAM per guess, which is what makes GPU cracking expensive. It is
in the standard library, so this matches the deliberate stdlib-only choice
documented in session_tokens.py:9-11 rather than pulling in bcrypt/argon2.

argon2id would be marginally better, but it is a compiled dependency and scrypt
at these parameters is a legitimate choice, not a compromise.

Stored format is self-describing so the parameters can be raised later without
invalidating anyone's password:

    scrypt$16384$8$1$<salt_b64>$<hash_b64>

verify() reads the cost from the stored string, so an old hash keeps verifying
after the defaults change. needs_rehash() tells the caller when to transparently
upgrade one on next successful login.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from typing import Final

# n=16384 (2^14), r=8, p=1 → ~16 MB per hash, a few ms on the API box.
# The memory cost is the point: it is what an attacker cannot parallelise away.
_N: Final = 16384
_R: Final = 8
_P: Final = 1
_SALT_BYTES: Final = 16
_KEY_LEN: Final = 32
_MAXMEM: Final = 64 * 1024 * 1024  # headroom over n*r*128 so scrypt doesn't refuse

MIN_PASSWORD_LEN: Final = 8
MAX_PASSWORD_LEN: Final = 200  # bound the work an unauthenticated caller can ask for


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str, *, n: int = _N, r: int = _R, p: int = _P) -> str:
    """Hash a password for storage. Salt is generated per call."""
    if not isinstance(password, str) or not password:
        raise ValueError("password required")
    pw = password.encode("utf-8")
    if len(pw) > MAX_PASSWORD_LEN * 4:
        raise ValueError("password too long")
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.scrypt(pw, salt=salt, n=n, r=r, p=p, maxmem=_MAXMEM, dklen=_KEY_LEN)
    return f"scrypt${n}${r}${p}${_b64e(salt)}${_b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of a password against a stored hash.

    Never raises: a malformed or unknown-format hash is a failed login, not a
    500. Returns False for anything it cannot parse.
    """
    try:
        if not password or not stored:
            return False
        parts = stored.split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt, expected = _b64d(parts[4]), _b64d(parts[5])
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=_MAXMEM, dklen=len(expected)
        )
        # compare_digest, not ==: an early-exit compare leaks the hash byte by byte.
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def needs_rehash(stored: str) -> bool:
    """True when a stored hash predates the current cost parameters."""
    try:
        parts = stored.split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return True
        return (int(parts[1]), int(parts[2]), int(parts[3])) != (_N, _R, _P)
    except Exception:
        return True


def new_email_token() -> tuple[str, str]:
    """(token_for_the_email, sha256_hex_for_the_db).

    Only the hash is stored, exactly like a password: a dump of
    auth_email_tokens must not hand out working reset links.
    """
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode("ascii")).hexdigest()


def hash_email_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("ascii")).hexdigest()


# ── Validation ───────────────────────────────────────────────────────────────
# Kept here so the rules live next to the hashing rather than in a handler.

_USERNAME_MIN: Final = 3
_USERNAME_MAX: Final = 24


def validate_username(username: str) -> tuple[bool, str]:
    u = (username or "").strip()
    if len(u) < _USERNAME_MIN:
        return False, f"Username must be at least {_USERNAME_MIN} characters."
    if len(u) > _USERNAME_MAX:
        return False, f"Username must be at most {_USERNAME_MAX} characters."
    if not all(c.isalnum() or c in "_-" for c in u):
        return False, "Username can use letters, numbers, underscore and hyphen only."
    if not any(c.isalnum() for c in u):
        return False, "Username needs at least one letter or number."
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    p = password or ""
    if len(p) < MIN_PASSWORD_LEN:
        return False, f"Password must be at least {MIN_PASSWORD_LEN} characters."
    if len(p) > MAX_PASSWORD_LEN:
        return False, f"Password must be at most {MAX_PASSWORD_LEN} characters."
    return True, ""


def validate_email(email: str) -> tuple[bool, str]:
    """Deliberately permissive. The real proof that an address works is that a
    verification mail arrives — a clever regex only rejects valid addresses."""
    e = (email or "").strip()
    if not e:
        return False, "Email is required so you can recover your account."
    if len(e) > 190:
        return False, "That email address is too long."
    if e.count("@") != 1:
        return False, "That doesn't look like an email address."
    local, _, domain = e.partition("@")
    if not local or not domain or "." not in domain or domain.startswith(".") or domain.endswith("."):
        return False, "That doesn't look like an email address."
    return True, ""
