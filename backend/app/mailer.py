"""Resend delivery. Every draft goes to DEMO_INBOX; company-pack emails are display-only."""
import logging

import httpx

from .config import env

log = logging.getLogger("footnote.mailer")
URL = "https://api.resend.com/emails"
SENDER = "Footnote <onboarding@resend.dev>"

_client: httpx.AsyncClient | None = None


class MailError(RuntimeError):
    pass


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=4.5)
    return _client


async def warm_up() -> None:
    """Open the TLS connection ahead of the first real request (best effort)."""
    try:
        await _http().get("https://api.resend.com/")
    except httpx.HTTPError:
        pass


async def send(subject: str, body: str, display_to: str, draft_id: str) -> None:
    key, inbox = env("RESEND_API_KEY"), env("DEMO_INBOX")
    if not key or not inbox:
        raise MailError("RESEND_API_KEY and DEMO_INBOX must be set")
    http = _http()
    text = f"{body}\n\n--\nDemo note: this would be delivered to {display_to}; sent to the demo inbox instead."
    try:
        r = await http.post(URL, headers={"Authorization": f"Bearer {key}",
                                          "Idempotency-Key": draft_id},
                            json={"from": SENDER, "to": [inbox], "subject": subject, "text": text})
    except httpx.HTTPError as e:
        raise MailError(f"Resend request failed: {type(e).__name__}") from e
    if r.status_code >= 300:
        log.warning("Resend HTTP %s: %s", r.status_code, r.text[:200])
        raise MailError(f"Resend returned HTTP {r.status_code}")
