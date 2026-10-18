# Footnote

Even G2 smart-glasses app for new hires. During a meeting it listens, detects
unfamiliar company terms, shows one line on the glasses (meaning + owner),
lets the user queue a question with one press, and after the meeting sends
each owner one batched message. Terms fade out after 3 sightings or a mute.
Demo company: "Halcyon Robotics" (synthetic data in /data/company_pack.json).

## Repo layout (stay in your folder)
/glasses  TypeScript, Vite, @evenrealities/even_hub_sdk. Owner: Sohail.
/web      Digest page (React + Vite). Owner: Sohail.
/backend  Python 3.11 FastAPI. Owner: Kartik.
/agent    Fetch.ai uAgent (chat protocol, mailbox). Owner: Kartik.
/data     company_pack.json. Owner: Kartik.
Never edit another owner's folder. If you need a contract change, stop and say so.

## API contract (frozen; backend base URL in env BACKEND_URL, HTTPS)
POST /session/start                      -> {session_id}
POST /listen?session_id=ID               body: raw PCM bytes (16 kHz, s16le, mono, ~4 s)
                                         -> {transcript, cards: Card[]}
POST /listen_text {session_id, text}     -> {transcript, cards: Card[]}   (testing + fallback)
POST /cards/{card_id}/queue {session_id} -> {queued: true, owner_name}
POST /terms/{term_id}/mute               -> {muted: true}
POST /session/{session_id}/end           -> {drafts: Draft[]}
POST /drafts/{draft_id}/send             -> {sent: true}
POST /drafts/{draft_id}/discard          -> {discarded: true}
GET  /digest                             -> {terms_learned[], people_to_meet[], sent[]}
GET  /health                             -> {ok: true}

Card  = {card_id, term_id, term, line1, owner_name, owner_team, source: "glossary"|"llm", confidence}
        term <= 24 chars, line1 <= 44 chars, owner_name + owner_team <= 40 chars
Draft = {draft_id, to_name, to_email, subject, body, terms[]}

Discard is allowed only after the meeting ends and before send. A sent draft
returns 409. A discarded draft is omitted from repeated /end responses and
cannot be sent (409). It is not shown as pending in /digest.

A term is never returned as a card if muted or seen >= 3 times.
The backend never returns more than 2 cards per /listen call.
The glossary fast path returns immediately. StepFun (slow path) runs in the
background, capped at 25 s; its cards are returned with the first /listen
response after the explanation is ready. Drafts start when a question is queued;
/session/{session_id}/end returns the saved draft or its template promptly.

## Hard rules
- No API keys in /glasses or /web. All third-party calls go through /backend.
- Backend sends CORS headers for every origin and answers OPTIONS preflights.
- Glasses UI: plain text only, no bold/size control; brightness via textColor 0-4.
- Root-page double press calls shutDownPageContainer(1). Never exit silently.
- Target: glossary card on glasses within 3 s of the word being spoken;
  uncatalogued StepFun terms appear after background inference finishes.
- Email: Resend API only; every draft goes to env DEMO_INBOX. Company-pack emails are display-only.
- Logging: plain Python logging with per-step timings (stt_ms, match_ms, llm_ms). No Sentry.
- Prefer the simplest thing that demos reliably. No new dependencies without reason.

## Backend env vars (/backend/.env, never committed)
ELEVENLABS_API_KEY, STEPFUN_API_KEY, RESEND_API_KEY, DEMO_INBOX,
ASI_ONE_API_KEY, AGENTVERSE_API_KEY (last two only for the Fetch.ai stretch)
