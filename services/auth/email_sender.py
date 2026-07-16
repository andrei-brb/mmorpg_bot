"""Transactional email — Resend over the aiohttp we already ship.

No new dependency: Resend is a plain REST API and `aiohttp` is already in
requirements.txt for the Vercel render calls.

Two drivers behind one seam:
  ResendSender  — real, needs RESEND_API_KEY + a domain you verified with them.
  LogSender     — the default when no key is set. Logs the mail (including the
                  reset link) instead of sending it, so signup and password
                  recovery can be built and tested end-to-end with no account.

The seam is what matters: nothing above this file knows which one is running,
so shipping a key later is config, not code.
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Protocol

log = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com/emails"


class EmailSender(Protocol):
    async def send(self, *, to: str, subject: str, html: str, text: str) -> bool: ...


class LogSender:
    """Development default. Prints what would have been sent.

    Deliberately logs the body: without it a developer with no Resend key could
    never complete a password reset locally. This is why it must never be the
    driver in production — see get_email_sender().
    """

    async def send(self, *, to: str, subject: str, html: str, text: str) -> bool:
        log.warning(
            "EMAIL NOT SENT (no RESEND_API_KEY) — would have sent to %s\n  subject: %s\n  body:\n%s",
            to,
            subject,
            text,
        )
        return True


class ResendSender:
    def __init__(self, api_key: str, from_addr: str):
        self._key = api_key
        self._from = from_addr

    async def send(self, *, to: str, subject: str, html: str, text: str) -> bool:
        import aiohttp

        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    RESEND_API,
                    headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
                    json={"from": self._from, "to": [to], "subject": subject, "html": html, "text": text},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    if r.status < 300:
                        return True
                    body = await r.text()
                    # Do not surface provider errors to the caller: whether an
                    # address exists is not something an anonymous request
                    # should be able to probe.
                    log.error("resend send failed %s: %s", r.status, body[:300])
                    return False
        except Exception as e:
            log.error("resend send error: %s", e)
            return False


_sender: Optional[EmailSender] = None


def get_email_sender() -> EmailSender:
    """Resend when configured, otherwise the logging stub."""
    global _sender
    if _sender is not None:
        return _sender
    key = (os.getenv("RESEND_API_KEY") or "").strip()
    from_addr = (os.getenv("EMAIL_FROM") or "").strip()
    if key and from_addr:
        log.info("email: Resend driver (from=%s)", from_addr)
        _sender = ResendSender(key, from_addr)
    else:
        # Loud on purpose. Silently not sending password resets in production
        # would look like "reset is broken" and be very hard to diagnose.
        log.warning(
            "email: no RESEND_API_KEY/EMAIL_FROM — password reset mail will be LOGGED, not sent."
        )
        _sender = LogSender()
    return _sender


def reset_url(token: str) -> str:
    base = (os.getenv("PUBLIC_APP_URL") or "").strip().rstrip("/")
    return f"{base}/reset?token={token}" if base else f"(set PUBLIC_APP_URL) token={token}"


def verify_url(token: str) -> str:
    base = (os.getenv("PUBLIC_APP_URL") or "").strip().rstrip("/")
    return f"{base}/verify?token={token}" if base else f"(set PUBLIC_APP_URL) token={token}"


async def send_password_reset(to: str, username: str, token: str) -> bool:
    link = reset_url(token)
    return await get_email_sender().send(
        to=to,
        subject="Reset your Emberlone password",
        text=(
            f"Hello {username},\n\n"
            f"Someone asked to reset the password for your Emberlone account.\n"
            f"Open this link within one hour to choose a new one:\n\n{link}\n\n"
            f"If that wasn't you, ignore this email — nothing has changed and your "
            f"character is untouched.\n"
        ),
        html=(
            f"<p>Hello {username},</p>"
            f"<p>Someone asked to reset the password for your Emberlone account. "
            f"Open this link within one hour to choose a new one:</p>"
            f'<p><a href="{link}">Reset my password</a></p>'
            f"<p style='color:#777'>If that wasn't you, ignore this email — nothing has "
            f"changed and your character is untouched.</p>"
        ),
    )


async def send_email_verify(to: str, username: str, token: str) -> bool:
    link = verify_url(token)
    return await get_email_sender().send(
        to=to,
        subject="Confirm your Emberlone email",
        text=(
            f"Hello {username},\n\n"
            f"Confirm this address so you can recover your account if you ever "
            f"forget your password:\n\n{link}\n\n"
            f"You can keep playing without confirming — but recovery won't work until you do.\n"
        ),
        html=(
            f"<p>Hello {username},</p>"
            f"<p>Confirm this address so you can recover your account if you ever forget "
            f"your password:</p>"
            f'<p><a href="{link}">Confirm my email</a></p>'
            f"<p style='color:#777'>You can keep playing without confirming — but recovery "
            f"won't work until you do.</p>"
        ),
    )
