"""Footnote backend: the frozen API contract from CLAUDE.md."""
import asyncio
import json
import logging
import math
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from . import config, llm, mailer, stt
from .db import Store, clip
from .matcher import Matcher, tokens

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("footnote")

MAX_CARDS_PER_LISTEN = 2
SLOW_PATH_CAP_S = 25.0  # background work; never holds up /listen
DRAFT_CAP_S = 12.0  # starts when a card is queued, not when the meeting ends
STT_CAP_S = 4.5
SEND_CAP_S = 4.5
MAX_PCM_BYTES = 2_000_000
MAX_TEXT_CHARS = 4_096
MAX_TEXT_BODY_BYTES = 32_768
MIN_PCM_BYTES = 3_200  # 0.1 s; anything shorter is not worth an STT call
MIN_CONFIDENCE = 0.6
CODE_TERM = re.compile(r"[A-Z]{2,5}-[0-9]+")


def is_unexplained_word(term: str, meaning: str) -> bool:
    return not CODE_TERM.fullmatch(term.upper()) and \
        clip(meaning, 44).lower() == "internal code; details unconfirmed"


@dataclass
class Session:
    id: str
    ended: bool = False
    ending: bool = False
    pending: list[str] = field(default_factory=list)   # term ids waiting for the next response
    shown: set[str] = field(default_factory=set)       # one card per term per meeting
    tail: bytes = b""                                  # end of the previous chunk (word-boundary overlap)
    tasks: set = field(default_factory=set)            # background slow-path tasks
    draft_tasks: dict[str, asyncio.Task] = field(default_factory=dict)
    end_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class State:
    def __init__(self, store: Store):
        self.store = store
        self.sessions: dict[str, Session] = {}
        self.send_locks: dict[str, asyncio.Lock] = {}
        self.system_prompt = llm.pack_prompt(store.pack)
        self.people_words = {w for p in store.people_text() for w in tokens(p["name"])}
        self._matcher: Matcher | None = None
        self._matcher_version = -1

    def matcher(self) -> Matcher:
        if self._matcher is None or self._matcher_version != self.store.terms_version:
            # Ignore old speculative cache entries without deleting queued history.
            self._matcher = Matcher([t for t in self.store.all_terms()
                                     if t["source"] != "llm" or not is_unexplained_word(t["term"], t["meaning"])])
            self._matcher_version = self.store.terms_version
        return self._matcher

    def session(self, session_id: str) -> Session:
        s = self.sessions.get(session_id)
        if s:
            return s
        row = self.store.session(session_id)
        if not row:
            raise HTTPException(404, "Unknown session")
        s = self.sessions[session_id] = Session(
            session_id, ended=row["ended_at"] is not None,
            shown=self.store.shown_for_session(session_id))
        return s


def get_state(request: Request) -> State:
    return request.app.state.footnote


async def read_limited_body(request: Request, limit: int) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise HTTPException(413, "Request body too large")
        body.extend(chunk)
    return bytes(body)


# --------------------------------------------------------------------- core
def collect_cards(st: State, s: Session, new_ids: list[str]) -> list[dict]:
    """Issue waiting cards on the next response, then this chunk's new hits."""
    ordered = list(dict.fromkeys(s.pending + new_ids))
    chosen, waiting = [], []
    for tid in ordered:
        if tid in s.shown or st.store.is_hidden(tid):
            continue
        term = st.store.term(tid)
        if term["source"] == "llm" and is_unexplained_word(term["term"], term["meaning"]):
            continue
        (chosen if len(chosen) < MAX_CARDS_PER_LISTEN else waiting).append(tid)
    s.pending = waiting
    cards = []
    for tid in chosen:
        st.store.bump_seen(tid)
        s.shown.add(tid)
        cards.append(st.store.make_card(s.id, tid))
    return cards


async def slow_path(st: State, s: Session, transcript: str) -> None:
    """StepFun explains unknown capitalized words / acronyms. Never blocks a response:
    capped at 25 s, and its cards ride along with the next /listen after completion."""
    if not config.env("STEPFUN_API_KEY"):
        return
    known = st.matcher().known_words
    cands = llm.find_candidates(transcript, known, st.people_words)
    if not cands:
        return
    t0 = time.perf_counter()
    try:
        items = await asyncio.wait_for(llm.explain(st.system_prompt, transcript, cands), SLOW_PATH_CAP_S)
    except asyncio.TimeoutError:
        log.warning("slow path session=%s llm_ms>%d (capped)", s.id, SLOW_PATH_CAP_S * 1000)
        items = []
    except Exception as e:  # StepFun down or bad key: the fast path keeps working
        log.warning("slow path session=%s failed: %s; cause=%s", s.id, type(e).__name__, e.__cause__)
        items = []
    by_name = {"".join(tokens(str(item.get("term", "")))): item for item in items}
    words = {word.lower() for word in tokens(transcript)}
    named_people = [p["id"] for p in st.store.people_text() if p["name"].split()[0].lower() in words]
    hinted_owner = named_people[0] if len(named_people) == 1 else None
    work_context = bool(words & {"runbook", "update", "updated", "status", "ready", "deploy", "down", "incident"})
    people_ids = {p["id"] for p in st.store.people_text()}
    added = []
    for word in cands:
        item = by_name.get("".join(tokens(word)), {})
        contextual_code = bool(CODE_TERM.fullmatch(word) and hinted_owner and work_context)
        raw_confidence = item.get("confidence")
        raw_meaning = item.get("meaning")
        owner = item.get("owner_id")
        if item.get("is_company_term") is not True and not contextual_code:
            continue
        if not (isinstance(owner, str) and owner in people_ids):
            owner = hinted_owner if contextual_code else None
        if not (isinstance(raw_meaning, str) and clip(raw_meaning, 44)):
            raw_meaning = "Internal code; details unconfirmed" if CODE_TERM.fullmatch(word) else ""
        if is_unexplained_word(word, raw_meaning):
            continue
        confidence = raw_confidence if isinstance(raw_confidence, (int, float)) \
            and not isinstance(raw_confidence, bool) and math.isfinite(raw_confidence) else None
        if confidence is None and raw_confidence == "low":
            confidence = MIN_CONFIDENCE
        if confidence is None and contextual_code:
            confidence = MIN_CONFIDENCE
        if not (owner and raw_meaning and confidence is not None and MIN_CONFIDENCE <= confidence <= 1.0):
            continue
        confidence = min(confidence, 0.7)  # every uncatalogued meaning is an inference
        if s.ending or s.ended:
            return
        name = str(item.get("term") or word).strip()
        tid = st.store.add_llm_term(name, clip(raw_meaning, 44), owner, confidence)
        if tid not in s.pending:
            s.pending.append(tid)
        added.append(word)
    log.info("slow path session=%s llm_ms=%d candidate_count=%d added_count=%d", s.id,
             (time.perf_counter() - t0) * 1000, len(cands), len(added))


async def respond(st: State, s: Session, transcript: str, stt_ms: int = 0) -> dict:
    if s.ended or s.ending:
        raise HTTPException(409, "Session already ended")
    t0 = time.perf_counter()
    matching_text = llm.normalize_spoken_codes(transcript)
    ids = st.matcher().find(matching_text) if matching_text else []
    match_ms = (time.perf_counter() - t0) * 1000
    cards = collect_cards(st, s, ids)
    if transcript:
        task = asyncio.create_task(slow_path(st, s, matching_text))
        s.tasks.add(task)
        task.add_done_callback(s.tasks.discard)
    log.info("listen session=%s stt_ms=%d match_ms=%.1f cards=%s", s.id, stt_ms, match_ms,
             [c["term"] for c in cards])
    return {"transcript": transcript, "cards": cards}


def subject_for(short: str, terms: list[str]) -> str:
    if len(terms) == 1:
        about = terms[0]
    elif len(terms) == 2:
        about = f"{terms[0]} and {terms[1]}"
    else:
        about = f"{terms[0]}, {terms[1]} and {len(terms) - 2} more"
    return f"To {short}: quick question about {about}"


async def build_draft(st: State, owner_id: str, items: list) -> tuple[str, str, str]:
    owner = dict(st.store.person(owner_id))
    names = [i["term"] for i in items]
    new_hire = config.env("NEW_HIRE_NAME", "Alex")
    t0 = time.perf_counter()
    try:
        body = await asyncio.wait_for(
            llm.draft_message(owner, [dict(i) for i in items], new_hire, st.system_prompt), DRAFT_CAP_S)
        source = "stepfun"
    except Exception as e:
        log.warning("draft for %s fell back to template (%s)", owner["short_name"], type(e).__name__)
        body, source = "", "template"
    if not body.strip():
        body, source = llm.template_message(owner["name"].split()[0], names, new_hire), "template"
    log.info("draft owner=%s source=%s llm_ms=%d", owner["short_name"], source, (time.perf_counter() - t0) * 1000)
    return owner_id, subject_for(owner["short_name"], names), body.strip()


def template_draft(st: State, owner_id: str, items: list) -> tuple[str, str, str]:
    owner = st.store.person(owner_id)
    names = [i["term"] for i in items]
    return (owner_id, subject_for(owner["short_name"], names),
            llm.template_message(owner["name"].split()[0], names, config.env("NEW_HIRE_NAME", "Alex")))


async def refresh_draft(st: State, s: Session, owner_id: str, items: list) -> None:
    """Replace the saved template only while this exact queue is still open."""
    try:
        _, subject, body = await build_draft(st, owner_id, items)
        if not s.ending and not s.ended:
            st.store.update_preview_if_current(s.id, owner_id, subject, body)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.warning("draft refresh failed session=%s owner=%s error=%s", s.id, owner_id, type(e).__name__)


def schedule_draft(st: State, s: Session, owner_id: str, items: list) -> None:
    previous = s.draft_tasks.get(owner_id)
    if previous and not previous.done():
        previous.cancel()
    if not config.env("STEPFUN_API_KEY"):
        s.draft_tasks.pop(owner_id, None)
        return
    task = asyncio.create_task(refresh_draft(st, s, owner_id, items))
    s.draft_tasks[owner_id] = task

    def clear(done: asyncio.Task) -> None:
        if s.draft_tasks.get(owner_id) is done:
            s.draft_tasks.pop(owner_id, None)

    task.add_done_callback(clear)


# --------------------------------------------------------------------- app
class QueueBody(BaseModel):
    session_id: str


def create_api(db_path: str | None = None, pack_path=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(db_path or config.db_path(), pack_path or config.pack_path())
        app.state.footnote = State(store)
        log.info("ready: %d people, %d terms; elevenlabs=%s stepfun=%s resend=%s", len(store.people_text()),
                 len(store.all_terms()), bool(config.env("ELEVENLABS_API_KEY")),
                 bool(config.env("STEPFUN_API_KEY")), bool(config.env("RESEND_API_KEY")))
        warm = [fn() for key, fn in (("ELEVENLABS_API_KEY", stt.warm_up), ("RESEND_API_KEY", mailer.warm_up),
                                     ("STEPFUN_API_KEY", llm.warm_up)) if config.env(key)]
        app.state.warm_up = asyncio.gather(*warm)  # first real request should not pay for TLS setup
        yield
        app.state.warm_up.cancel()
        for session in app.state.footnote.sessions.values():
            for task in [*session.tasks, *session.draft_tasks.values()]:
                task.cancel()
        store.conn.close()

    api = FastAPI(title="Footnote backend", lifespan=lifespan)

    @api.get("/health")
    async def health():
        return {"ok": True}

    @api.post("/session/start")
    async def session_start(request: Request):
        st = get_state(request)
        sid = st.store.create_session()
        st.sessions[sid] = Session(sid)
        return {"session_id": sid}

    @api.post("/listen")
    async def listen(session_id: str, request: Request):
        st = get_state(request)
        s = st.session(session_id)
        if s.ended or s.ending:
            raise HTTPException(409, "Session already ended")
        pcm = await read_limited_body(request, MAX_PCM_BYTES)
        if len(pcm) % 2:
            raise HTTPException(400, "Audio chunk must contain complete 16-bit samples")
        transcript, stt_ms = "", 0
        if len(pcm) >= MIN_PCM_BYTES and not stt.is_silent(pcm):
            t0 = time.perf_counter()
            try:
                transcript = await asyncio.wait_for(stt.transcribe(s.tail + pcm), STT_CAP_S)
            except (stt.SttError, asyncio.TimeoutError) as e:
                log.warning("stt failed session=%s: %s", session_id, e)
                raise HTTPException(502, "Speech-to-text failed")
            stt_ms = int((time.perf_counter() - t0) * 1000)
        overlap = int(config.env("OVERLAP_MS", "400")) * 32  # 16 kHz * 2 bytes per ms
        s.tail = pcm[-overlap:] if overlap > 0 else b""  # keeps a word split across chunks intact
        return await respond(st, s, transcript, stt_ms)

    @api.post("/listen_text")
    async def listen_text(request: Request):
        raw = await read_limited_body(request, MAX_TEXT_BODY_BYTES)
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(422, "Invalid JSON body")
        if not isinstance(body, dict) or not isinstance(body.get("session_id"), str) or not isinstance(body.get("text"), str):
            raise HTTPException(422, "session_id and text must be strings")
        if len(body["text"]) > MAX_TEXT_CHARS:
            raise HTTPException(422, "Text is too long")
        st = get_state(request)
        return await respond(st, st.session(body["session_id"]), body["text"].strip())

    @api.post("/cards/{card_id}/queue")
    async def queue_card(card_id: str, body: QueueBody, request: Request):
        st = get_state(request)
        card = st.store.card(card_id)
        if not card or card["session_id"] != body.session_id:
            raise HTTPException(404, "Unknown card")
        session = st.session(body.session_id)
        if session.ended or session.ending:
            raise HTTPException(409, "Session already ended")
        t = st.store.term(card["term_id"])
        added = st.store.queue_card(body.session_id, card["term_id"], t["owner_id"])
        items = st.store.queued_by_owner(body.session_id)[t["owner_id"]]
        owner_id, subject, template = template_draft(st, t["owner_id"], items)
        st.store.save_preview_draft(body.session_id, owner_id, subject, template)
        if added:
            schedule_draft(st, session, owner_id, items)
        return {"queued": True, "owner_name": clip(t["owner_name"], 40)}

    @api.post("/terms/{term_id}/mute")
    async def mute_term(term_id: str, request: Request):
        if not get_state(request).store.mute(term_id):
            raise HTTPException(404, "Unknown term")
        return {"muted": True}

    @api.post("/session/{session_id}/end")
    async def end_session(session_id: str, request: Request):
        st = get_state(request)
        s = st.session(session_id)
        async with s.end_lock:  # a double press must not draft twice
            grouped = st.store.queued_by_owner(session_id)
            prepared = [template_draft(st, owner, items) for owner, items in grouped.items()]
            if st.store.session(session_id)["ended_at"] is None or \
                    set(grouped) - st.store.draft_owners(session_id):
                s.ending = True
                try:
                    for task in list(s.tasks):
                        task.cancel()
                    for task in list(s.draft_tasks.values()):
                        task.cancel()
                    st.store.complete_session(session_id, prepared)
                    s.ended = True
                finally:
                    s.ending = False
            return {"drafts": st.store.drafts_for_session(session_id)}

    @api.post("/drafts/{draft_id}/send")
    async def send_draft(draft_id: str, request: Request):
        st = get_state(request)
        if not st.store.draft(draft_id):
            raise HTTPException(404, "Unknown draft")
        lock = st.send_locks.setdefault(draft_id, asyncio.Lock())
        async with lock:  # a double click must not send twice
            row = st.store.draft(draft_id)
            if st.store.session(row["session_id"])["ended_at"] is None:
                raise HTTPException(409, "End the meeting before sending")
            if row["status"] != "sent":
                person = st.store.person(row["owner_id"])
                try:
                    await asyncio.wait_for(
                        mailer.send(row["subject"], row["body"], person["email"], draft_id),
                        SEND_CAP_S)
                except (mailer.MailError, asyncio.TimeoutError) as e:
                    log.warning("send failed draft=%s: %s", draft_id, e)
                    raise HTTPException(502, "Email delivery failed; the draft is kept, try again")
                st.store.mark_sent(draft_id)
                log.info("sent draft=%s to demo inbox (display to=%s)", draft_id, person["email"])
        return {"sent": True}

    @api.get("/digest")
    async def digest(request: Request):
        return get_state(request).store.digest()

    @api.post("/debug/reset")
    async def debug_reset(request: Request):
        """Rehearsal helper: clear sightings, mutes, meetings and drafts. Off unless ENABLE_DEBUG_RESET=1."""
        if config.env("ENABLE_DEBUG_RESET") != "1":
            raise HTTPException(404, "Not found")
        st = get_state(request)
        for session in st.sessions.values():
            for task in [*session.tasks, *session.draft_tasks.values()]:
                task.cancel()
        st.store.reset()
        st.sessions.clear()
        return {"reset": True}

    return api


class CorsEverywhere:
    """Outermost ASGI wrapper: answers every OPTIONS preflight with 204 and adds CORS
    headers to every response, including errors raised inside the app."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.inner(scope, receive, send)
        headers = [(b"access-control-allow-origin", b"*"), (b"access-control-expose-headers", b"*")]
        if scope["method"] == "OPTIONS":
            asked = dict(scope["headers"]).get(b"access-control-request-headers", b"*")
            headers += [(b"access-control-allow-methods", b"GET, POST, PUT, PATCH, DELETE, OPTIONS"),
                        (b"access-control-allow-headers", asked),
                        (b"access-control-allow-private-network", b"true"),
                        (b"access-control-max-age", b"86400"), (b"content-length", b"0")]
            await send({"type": "http.response.start", "status": 204, "headers": headers})
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_with_cors(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []), *headers]}
            await send(message)

        await self.inner(scope, receive, send_with_cors)

    def __getattr__(self, name):  # lets tests reach app.state etc.
        return getattr(self.inner, name)


def create_app(db_path: str | None = None, pack_path=None):
    return CorsEverywhere(create_api(db_path, pack_path))


app = create_app()
