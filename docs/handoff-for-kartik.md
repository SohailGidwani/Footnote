# Footnote handoff for Kartik

API contract changes: none. Read `CLAUDE.md` and `backend/HANDOFF.md` first.
Record any proposed contract change at the top of this file before changing it.

## Status and evidence

- Baseline: `50b146e` (Kartik's backend push). No application/backend code changed
  since that push; this handoff adds documentation only. Sohail's checkout also
  has earlier uncommitted README edits, separate from this handoff; do not include them.
- Verified here: backend `.venv/bin/python -m pytest -q`: **41 passed**, one
  dependency deprecation warning. Tests do not use real provider services.
- Verified here: local `/health` returned 200 and `{"ok":true}`; `OPTIONS /listen`
  returned 204 with the expected CORS origin, method and content-type headers.
- Verified here against the real local backend, not mock responses: typed phrase
  -> Bluebird + FCS cards -> queue Bluebird -> mute FCS -> end meeting -> one
  Priya draft -> digest containing both terms and their owners. No draft was sent.
- Verified here: the official simulator rendered both backend cards and meanings,
  queue confirmation, swipe-up to FCS, swipe-down mute, and long-press end with a
  Priya draft. This was typed-only; simulator microphone capture was disabled.
- Verified on physical G2 through a user-started cloudflared tunnel, confirmed by
  Sohail: typed phrases and real speech both produce cards with meanings on glasses.
- NOT tested on G2: queue, mute/fade-out, swipe up, long press, end meeting,
  draft approval, Resend delivery from the app, StepFun slow-path cards, latency.
- Sohail will test G2 queue -> draft -> email after his nap. **Do not spend time
  on that device flow.** The G2 and developer-mode phone are with Sohail.
- Live StepFun inference, Docker build/deployment, live Beta installation,
  Fetch.ai and measured end-to-end latency remain untested. Anything not explicitly
  listed as verified above is untested; do not infer success from mock/unit tests.
- All Footnote servers, simulator and tunnel were stopped. Client env files were
  restored to localhost. No backend bug was identified during local integration.

## Run locally on macOS

Use Node 22.18+ and Python 3.11. Python 3.11 was supplied by `uv` on the test Mac.
From the repo root, create the backend venv and install its declared dependencies:

```sh
uv venv --python 3.11 backend/.venv
uv pip install --python backend/.venv/bin/python -r backend/requirements-dev.txt
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Reuse an existing working venv by running only the last three commands. Keep
`ELEVENLABS_API_KEY`, `STEPFUN_API_KEY`, `RESEND_API_KEY`, and `DEMO_INBOX` in
ignored `backend/.env`; add `ENABLE_DEBUG_RESET=1` for local rehearsals.
Real env files are not transferred by Git. Never copy secrets into either client.

In BOTH `glasses/.env.local` and `web/.env.local`, use:

```dotenv
BACKEND_URL=http://localhost:8000
MOCK_MODE=false
```

From the repo root, run `npm ci` if needed, then use separate terminals:

```sh
npm run dev          # phone/glasses client: 5173
npm run dev:web      # digest: 5174
npm run simulate    # official simulator; use this instead of Sohail's hardware
```

Check that only Footnote owns 5173 before starting; another Vite project can make
the server silently move ports. We enforced the ports during integration with
`npm run dev -w glasses -- --strictPort` and the equivalent `-w web` command.
Use the phone page's Start meeting, Pause listening, then "Try a phrase instead":
`Bluebird is slipping because FCS is still on the old golden path` -> Find terms.
The laptop browser has no glasses bridge; typed input remains usable after start.
Between rehearsals, reload the client and reset local state:

```sh
curl -X POST http://localhost:8000/debug/reset
```

Reset requires `ENABLE_DEBUG_RESET=1` and clears meetings, drafts, sightings and
mutes. Each term is issued once per meeting; muted/three-sighting terms stay hidden.
Restart the simulator after Vite reloads if startup reports an existing-page error.

No tunnel runs during laptop/simulator development. Only real G2 testing needs
HTTPS: Sohail starts `cloudflared tunnel --url http://localhost:8000`, puts its
printed origin in `glasses/.env.local`, restarts Vite, regenerates and rescans the
QR from the Even Hub tab. Leave the digest on localhost. Tunnel restarts require
a new env URL, Vite restart and QR rescan. Restore localhost after device testing.
Never put tunnel URLs, LAN IPs, inbox addresses or keys in tracked files/log evidence.

## Kartik's tasks, in order

1. **Prove live StepFun inference (required for the prize).** Reset, start a new
   session and POST `/listen_text` with that `session_id` and
   `Did Marcus update the HAL-9 runbook?`. Continue listen calls in the SAME session
   until inference finishes: the card arrives on the first listen AFTER completion,
   not necessarily the next call. The background cap is 12 seconds; keep the phone
   request timeout at 6 seconds. An empty-text `/listen_text` can collect ready cards.
   Confirm the HAL-9 card has `source: "llm"`; a glossary runbook card is not proof.
   Append sanitized request/result evidence, successful provider inference request
   and backend slow-path log lines with `llm_ms`. A warm-up `/models` response,
   template draft or unit test alone does not prove the model fired live.
2. **Set `NEW_HIRE_NAME=Sohail`** in local ignored `backend/.env` only;
   restart as needed and verify the intended draft signature. This is untested.
3. **Measure real-audio backend timings.** POST a real speech recording as raw
   16 kHz, signed 16-bit little-endian mono PCM to `/listen?session_id=...`.
   Normal chunks are 128,000 bytes (4 seconds). Record actual `stt_ms`, `match_ms`
   and `llm_ms` log lines and the returned cards; distinguish background inference
   from the immediate response. Target card-on-glasses time is about 4 seconds.
   Backend timings alone do not prove that target; G2 latency remains untested
   until Sohail measures it. Do not invent measurements from the chunk duration.

### Task 4: Fetch.ai agent, basic block (required tonight)

Goal: a Footnote agent registered on Agentverse that a user can find and chat
with in ASI:One. Build in `/agent` using Python 3.11 and `uagents`.
Follow the uAgents ASI:One example:

- `Agent(name, seed from env, port=8001, mailbox=True, publish_agent_details=True)`.
- Use `Protocol(spec=chat_protocol_spec)` with the chat protocol types from
  `uagents_core.contrib.protocols.chat`; acknowledge every `ChatMessage` with
  `ChatAcknowledgement`, reply with `TextContent`, then call
  `agent.include(protocol, publish_manifest=True)`.

Minimum behavior:

- "What does <term> mean at Halcyon?" -> meaning + owner + team.
- "What did I learn today?" / "Who should I meet?" -> summary from `GET /digest`.
- Anything else -> a short help message listing what it can do.

Read `data/company_pack.json` directly for term lookups. NEVER call
`/listen_text` for lookups: it records sightings and would make terms fade out
before they reach the glasses.

Config belongs in ignored `/agent/.env`, never committed: `AGENT_SEED`,
`BACKEND_URL` (`http://localhost:8000` for now; deployed URL on Sunday), and
`STEPFUN_API_KEY` if used for intent routing. StepFun intent classification is
encouraged for the prize; fall back to keyword matching if it fails.

Registration: run the agent, open its printed Agent Inspector link, choose
Connect -> Mailbox, open Agent Profile, and set a clear name
("Footnote Jargon Decoder") and handle. Write `/agent/README.md` for
the Agentverse listing with both badges:

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

Include a one-paragraph description, capability keywords and three example queries.
Done when ASI:One chat correctly answers "What does Bluebird mean at Halcyon?".
Record the Agentverse profile URL and a public ASI:One shared chat URL in the
changelog: both are required for Fetch submission and are fine to share.
The agent answers only while running; record where it runs in the changelog.
The implementation, local tests, mailbox connection and Bluebird ASI:One reply
are complete. Both public submission URLs are verified; Agentverse profile
name, handle and published README need account-side review.

## Rules while Sohail sleeps

- You own `/backend`, `/data`, `/agent`. Keep changes there by default.
- Fix `/glasses` or `/web` only for a client bug blocking task 1. Use branch
  `kartik/client-fix`, keep the diff minimal, and list EVERY changed file and
  behavior in the changelog below for Sohail to review. Do not merge it silently.
- Keep API paths/shapes frozen in `CLAUDE.md`; document any change at this file's top.
- Never commit real env files, keys, tunnel/deployment URLs, inbox addresses or LAN IPs.
- Record failed checks and provider errors honestly. Preserve drafts on send errors.

## Deferred: deployment (Sunday morning)

Deployment is deliberately the LAST hackathon step, done together Sunday morning,
not tonight. Build `backend/Dockerfile` from the repo root:
`docker build -f backend/Dockerfile -t footnote-backend .`.
Set `ELEVENLABS_API_KEY`, `STEPFUN_API_KEY`, `RESEND_API_KEY`, `DEMO_INBOX` and
`NEW_HIRE_NAME` as host secrets. Verify `/health` (200) and `OPTIONS /listen` (204)
with CORS origin/method/content-type headers. Share the URL privately, not in Git.
The final live Beta `.ehpk` bakes `BACKEND_URL` in at build time: deployment must
finish BEFORE the final Beta build, targeted for **10:30 AM Sunday**.
Container build, deployment and live Beta installation remain untested.

## Sohail after the nap

- Test queue -> end -> draft -> approve -> email, inbox/spam, and remaining gestures
  on real G2, including fade-out. These device checks are still untested.
- Live Beta builds wait for deployment on Sunday morning; until then, test on the G2 through the tunnel.
- Update README "Run on G2" using only observed results, then demo video and Devpost.

## Changelog for Kartik's agent

Append dated entries with task, files/branch, exact checks and results, sanitized
log timings, failures, outstanding work and any contract changes. Do not mark an
unrun check as passed.

### 2026-10-17 — Live StepFun slow-path proof

- Branch/files: `main`; documentation evidence appended to this file only. No API
  contract or application code changed.
- Started the local backend with the existing ignored `backend/.env`. Provider
  warm-up confirmed the StepFun models endpoint was reachable.
- Created a fresh session and sent `Did Marcus update the HAL-9 runbook?` through
  `/listen_text`. The immediate response contained the glossary `RUNBOOK` card.
- Polled the same session with empty text every two seconds. The fifth poll returned
  `HAL-9`, owner `Marcus L.` / `Platform`, `source: "llm"`, confidence `0.6`, and
  the cautious meaning `Internal code; details unconfirmed`.
- Sanitized backend evidence: StepFun chat completion returned HTTP 200; slow-path
  log recorded `llm_ms=9948`, `candidate_count=1`, `added_count=1`.
- Result: task 1 passed using live StepFun inference. No email was sent and no
  speech-to-text request was made. Real-audio timing and G2 slow-path latency remain
  outstanding. No secrets, session IDs, tunnel URLs or inbox addresses were recorded.

### 2026-10-17 — Local draft signature

- Added `NEW_HIRE_NAME=Sohail` to the ignored local `backend/.env` without displaying
  its contents. No tracked configuration or API code changed.
- Started the backend with provider keys disabled for this check, created a fresh
  session, queued the Bluebird card, and ended the meeting. The returned draft
  was addressed to Priya Raman, included Bluebird, and ended with `Sohail`.
- Result: task 2 passed for the template draft path. A live StepFun-written draft
  with this signature has not been tested. No email was sent.

### 2026-10-17 — Real recorded speech timing

- Converted a user-supplied 7.19-second Ogg/Opus speech recording to raw 16 kHz,
  signed 16-bit little-endian mono PCM. Sent it to the local backend as a
  128,000-byte (4-second) chunk and a 102,192-byte remainder in one fresh session.
- Both ElevenLabs speech-to-text requests returned HTTP 200. The first chunk
  returned Bluebird and FCS glossary cards; the second returned Golden Path.
- Backend logs: first chunk `stt_ms=572`, `match_ms=2.1`; second chunk
  `stt_ms=323`, `match_ms=1.2`. Local request wall times were 608 ms and 340 ms.
- Speech recognition included a short inaccurate phrase before “Blue Bird” in
  the first transcript, but all three intended glossary cards were detected.
  StepFun and email were disabled for this measurement, so no audio-triggered
  `llm_ms` was expected. These are backend timings, not card-on-glasses latency.
- Result: task 3 passed for this recording. G2 end-to-end latency remains
  unmeasured. The recording and converted PCM were not added to Git.

### 2026-10-17 — Local Fetch.ai agent implementation

- Added `/agent` with a local uAgents mailbox agent, Agent Chat Protocol
  handling, a read-only glossary lookup, and `/digest` answers. Its listing
  README includes the two required hackathon badges, keywords and examples.
- Generated a stable private seed in ignored `agent/.env`; it was not added to
  Git. `BACKEND_URL` remains `http://localhost:8000` for local development.
- Installed `uagents==0.26.1` with Python 3.11 and ran five local tests: all
  passed, including a chat message that received an acknowledgement and a
  Bluebird reply naming Priya Raman and Autonomy. The agent booted, printed an
  Inspector URL, and published `AgentChatProtocol` successfully.
- Agentverse reported `Agent mailbox not found` and a 401 while retrieving
  messages. The account-side **Connect > Mailbox** action is still required in
  a normal browser on this computer. The Codex in-app browser could not see
  the local agent endpoint. ASI:One chat, Agentverse profile URL and shared
  chat URL remain unverified/unrecorded. The agent ran locally on this Windows
  checkout; it has not been deployed.

### 2026-10-17 — Agentverse mailbox connected

- After the account-side Inspector connection, the running local agent logged
  `Successfully registered as mailbox agent in Agentverse`.
- `mailbox=True` was already present in `agent/agent.py`; the Inspector's
  configuration reminder required no code change or restart.
- A live ASI:One Bluebird chat and the public profile/chat URLs remain to be
  verified and recorded. The agent is still running locally for that check.

### 2026-10-17 — ASI:One Bluebird reply

- The user sent the Bluebird question in ASI:One and reported the reply:
  `Bluebird: v3 navigation stack rewrite. Owner: Priya Raman (Autonomy).`
  This matches `data/company_pack.json` and the local chat handler test.
- Agentverse mailbox registration was confirmed in the local agent log. The
  exact live chat reply is user-reported; the local handler does not currently
  log incoming chat text. The agent is running on this Windows checkout.
- The public ASI:One shared chat was checked in a signed-out browser and shows
  the Bluebird question and the exact reply above:
  https://asi1.ai/shared-chat/5242abb1-e546-46d2-ad8c-8a2b2600a1a8
- Public ASI:One agent page:
  https://asi1.ai/ai/agent1qg8amcyx59uvzkpj3zyy260cd790ewlf0nuga3qydevs25489lv3vgvx4gq
- Public Agentverse profile opened in a signed-out browser. It showed Active,
  Mailbox, AgentChatProtocol v0.3.0, the README badges and the Bluebird listing:
  https://agentverse.ai/agents/details/agent1qg8amcyx59uvzkpj3zyy260cd790ewlf0nuga3qydevs25489lv3vgvx4gq/profile
- The listing showed the correct README description and required badges, but
  its display name was still `footnote_new_hire` and its categories appeared
  unrelated. Agentverse profile details need account-side review before
  submission.
- Moved local setup instructions from the public `agent/README.md` listing to
  `agent/SETUP.md` so the listing focuses on user-facing capabilities. Restarted
  the agent with the same address; the public ASI:One listing still showed the
  old README after refresh. Save the shorter README through Agentverse's
  Overview editor, then recheck the public listing.
