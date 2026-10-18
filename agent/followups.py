"""Explicit, conversation-bound approval of existing meeting drafts."""
from __future__ import annotations

import json
import logging
import re
import secrets
import threading
import time
from urllib import error, request
from urllib.parse import urlsplit

from footnote import normalize_question

log = logging.getLogger("footnote.followups")
REVIEW_TTL_S = 600
MAX_CONVERSATIONS = 100
REVIEW_AGAIN = "No valid approval code for this conversation. Ask 'Show my saved questions' to preview again; then reply Approve followed by one code."


class Followups:
    def __init__(self, backend_url: str, token: str):
        self.backend_url = backend_url.rstrip("/")
        self.token = token.strip()
        self.reviews: dict[tuple[str, str], tuple[float, dict]] = {}
        self.lock = threading.Lock()

    def _request(self, path: str, method: str = "GET") -> dict:
        req = request.Request(self.backend_url + path, method=method,
                              headers={"Authorization": "Bearer " + self.token},
                              data=b"{}" if method == "POST" else None)
        with request.urlopen(req, timeout=8) as response:
            data = response.read(128_001)
        if len(data) > 128_000:
            raise ValueError("Oversized tool response")
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError("Invalid tool response")
        return value

    def _preview(self, key: tuple[str, str], now: float) -> str:
        self.reviews.pop(key, None)
        try:
            payload = self._request("/agent/drafts/pending")
            drafts, session = payload["drafts"], payload["session_id"]
            if not isinstance(drafts, list) or len(drafts) > 50:
                raise ValueError("Invalid drafts")
            if session is not None and (not isinstance(session, str) or not session):
                raise ValueError("Invalid session")
            if drafts and not session:
                raise ValueError("Missing meeting")
            ids = set()
            for draft in drafts:
                if not isinstance(draft, dict) or not all(
                    isinstance(draft.get(field), str) and 0 < len(draft[field]) <= 16_000
                    for field in ("draft_id", "to_name", "subject", "body")
                ) or not re.fullmatch(r"d_[A-Za-z0-9_-]{1,100}", draft["draft_id"]):
                    raise ValueError("Invalid draft")
                if draft["draft_id"] in ids:
                    raise ValueError("Duplicate draft")
                ids.add(draft["draft_id"])
        except (error.URLError, OSError, ValueError, KeyError, TypeError):
            log.warning("followups action=preview result=unavailable")
            return "I could not retrieve your pending drafts. Nothing sent. Please try 'Show my saved questions' again."
        if not drafts:
            return "There are no pending drafts in the latest ended meeting. Queue a question in Footnote and end that meeting first."
        choices = {}
        parts = ["Pending follow-ups from your latest ended meeting. Nothing sent yet.",
                 "Delivery goes to the configured demo inbox; coworkers below are display recipients only."]
        for draft in drafts:
            code = secrets.token_urlsafe(9)
            choices[code] = {**draft, "sent": False}
            parts.append(f"To: {draft['to_name']}\nSubject: {draft['subject']}\nBody:\n{draft['body']}\n\nTo send only this draft, reply: Approve {code}")
        if len(self.reviews) >= MAX_CONVERSATIONS:
            self.reviews.pop(next(iter(self.reviews)))
        self.reviews[key] = (now + REVIEW_TTL_S, choices)
        log.info("followups action=preview drafts=%d", len(choices))
        return "\n\n".join(parts) + "\n\nCodes expire in 10 minutes. Reply Cancel to leave drafts unsent."

    def reply(self, query: str, sender: str, conversation: str) -> str | None:
        question = normalize_question(query)
        lower = question.casefold()
        preview = bool(re.search(r"\b(show|review|send)\b", lower) and
                       re.search(r"\b(questions|drafts|follow[- ]?ups)\b", lower))
        action = lower.startswith(("approve", "cancel")) or lower in {"yes", "send", "send it", "confirm"}
        if not preview and not action:
            return None
        url = urlsplit(self.backend_url)
        if not self.token or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"} or not (
            url.scheme == "https" or url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            return "Follow-up tools are not configured. The operator must set the backend URL and shared agent token."
        if not sender or not conversation or conversation == "None":
            return "I need an ASI:One conversation to review and approve drafts. Please open a new chat."
        key = (sender, conversation)
        with self.lock:
            now = time.monotonic()
            self.reviews = {k: v for k, v in self.reviews.items() if v[0] > now}
            if preview:
                return self._preview(key, now)
            if re.fullmatch(r"cancel[.!]?", lower):
                self.reviews.pop(key, None)
                return "Cancelled this conversation's approvals. Nothing sent by this action; the drafts remain available on your phone."
            approval = re.fullmatch(r"approve\s+([A-Za-z0-9_-]{8,32})[.!]?", question, re.IGNORECASE)
            choices = self.reviews.get(key, (0, {}))[1]
            draft = choices.get(approval.group(1)) if approval else None
            if not draft:
                return REVIEW_AGAIN
            if draft["sent"]:
                return f"Already sent: {draft['subject']}. No additional email was requested."
            try:
                result = self._request(f"/drafts/{draft['draft_id']}/send", "POST")
                if result.get("sent") is not True:
                    raise ValueError("Unconfirmed send")
            except error.HTTPError as exc:
                if exc.code in {404, 409}:
                    choices.pop(approval.group(1), None)
                    return "This draft is no longer available to send. It may have been discarded on your phone. Preview your saved questions again."
                log.warning("followups action=send result=unconfirmed")
                return "I could not confirm email delivery. The approval is kept: retry the same Approve command to check safely. No automatic retry was made."
            except (error.URLError, OSError, ValueError):
                log.warning("followups action=send result=unconfirmed")
                return "I could not confirm email delivery. The approval is kept: retry the same Approve command to check safely. No automatic retry was made."
            draft["sent"] = True
            log.info("followups action=send result=confirmed")
            return f"Sent to the configured demo inbox. Display recipient: {draft['to_name']}. Subject: {draft['subject']}."
