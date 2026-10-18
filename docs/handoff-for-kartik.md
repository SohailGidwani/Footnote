# Footnote handoff for Kartik

## Approved additive API: ASI follow-up draft review (2026-10-18)

`GET /agent/drafts/pending` requires `Authorization: Bearer AGENT_API_TOKEN`.
Absent server token disables it (404); incorrect/missing authorization returns 401.
It returns `{session_id: string|null, drafts: Draft[]}` for only the most recently
ended meeting, excluding sent/discarded drafts. No request records sightings or
modifies drafts. The agent previews each draft and accepts an explicit, short-lived
`Approve <code>` bound to that sender/conversation before calling the existing
`POST /drafts/{draft_id}/send`. Cancel only clears that conversation's approvals.
Existing G2 endpoints, response shapes, email destination and Beta are unchanged.

## Design branch contract addition (kartik/design)

`POST /drafts/{draft_id}/discard` returns `{discarded: true}`. It is valid only
after `/session/{id}/end` and before the draft is sent. A sent or discarded draft
cannot be sent or discarded again as a new action (sent returns 409; discard is
idempotent). Discarded drafts are omitted from repeated `/end` responses and are
not marked as pending in `/digest`. The phone waits about five seconds before
calling discard so its Undo action can restore the draft.

Afterimage Paper screens and G2 preview:
https://app.paper.design/file/01M56HH1VJ2BSH57HAFMAF1RED/p-5-0
The design branch must stay separate from `main` until Sohail retests the full
loop on physical G2. The border and text fit need that device check.

API timing update (Sohail): background StepFun explanations are capped at 25 s
instead of 12 s; measured live Step-5 Preview calls took 15.7-16.5 s. Phone requests
still time out after 6 s. Paths and response shapes are unchanged. Inferred cards
suggest a person to ask; they do not confirm ownership. Read `CLAUDE.md` and
`backend/HANDOFF.md` first.
Record any proposed contract change at the top of this file before changing it.
The status below is the initial handoff snapshot; current changes are in the changelog.

Current Fetch agent: **Footnote Jargon Decoder**, `@footnote-jargon-decoder`,
now running on Railway. Do not run its local copy at the same time.
[ASI:One page](https://asi1.ai/ai/agent1qtm5jg9yr7e35ysxxahsvwc84g2yx95dkljesugg9xvdwmy8lp655tm2u2r).
Public demo chat: https://asi1.ai/shared-chat/886cf7a4-bd67-49f6-a14c-34ecbf9bcf07
Older agent links below are historical; see the identity replacement entry at the bottom.

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
   not necessarily the next call. The background cap is 25 seconds; keep the phone
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
are complete. Both public submission URLs are verified. The Agentverse name,
description and shorter README are live; ASI:One's agent page still shows its
older cached listing. The custom handle has not been independently verified.

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

### 2026-10-17 — Agentverse listing refreshed

- User updated the profile. In a signed-out browser, the public Agentverse
  profile showed **Footnote Jargon Decoder**, the short new-hire description,
  both badges, and only the three example questions in Agent Guide. The
  `Run locally` and `Connect to Agentverse` sections were gone. The profile
  was marked Active, ASI Available and Mailbox.
- The separate public ASI:One agent page still displayed the older
  `footnote_new_hire` name and setup sections at this check. This appears to
  be a listing sync delay; no change to the agent code was made. Recheck that
  page before submission. The user says the handle was changed, but the public
  pages inspected here did not expose its full value.

### 2026-10-17 — Sohail's generalized speech and StepFun fixes

- Sohail authorized backend/client fixes during G2 testing. Replaced the temporary
  HAL-9-specific substitution with general acronym + spoken-number normalization.
  Glossary matching also tolerates split/joined words without individual aliases;
  cached codes retain existing fuzzy matching for spoken variants. Unknown names
  can now be candidates at the start of a sentence. Raw transcripts stay unchanged.
- RUNBOOK already matched "run book"; its missing card was the intended fade-out
  after three sightings, confirmed by a read-only local database check.
- Live diagnostic: Step-5 Preview returned a Ridgeline meaning after 16.5 s but no
  owner. A shorter diagnostic prompt returned a meaning and suggested contact after
  15.7 s. A 512-token budget cut off the answer. Kept Step-5 Preview, increased only
  the background explanation cap to 25 s, and clarified suggested-contact selection.
  Phone timeout remains 6 s. Glasses label inferred contacts "Ask", not "Owner".
- Verification: 64 backend tests and 19 client tests pass; both client builds pass.
  Existing Starlette/httpx deprecation warning remains. No new dependencies.
- The full live API check with the updated code is NOT verified: an isolated
  temporary-database run failed with a TLS issuer error before StepFun inference.
  On the hotspot, direct DNS returned real StepFun servers while macOS application
  lookups intermittently returned WebFilter addresses. No certificate bypass or
  saved DNS change was made. An administrator cache reload still needs Sohail.
- Normal backend restarted on port 8000. No real meeting data was reset, no email
  was sent by these diagnostics, and no live Ridgeline card was cached in the app DB.
  These changes are local and uncommitted; G2 behavior after these edits needs testing.

### 2026-10-17 — Live Ridgeline API check passed after DNS cache reload

- Sohail ran the administrator DNS cache reload. Subsequent macOS lookups returned
  real StepFun servers and TLS verification succeeded. No saved DNS change was needed.
- Repeated the real `/session/start` -> `/listen_text` -> empty-text polls -> end
  flow against the current backend code with a temporary, isolated database.
  Phrase: `The Ridgeline migration moves our telemetry onto the new cluster.`
- Step-5 Preview chat completion returned HTTP 200. Backend evidence:
  `llm_ms=16495 candidate_count=1 added_count=1`. The next poll returned RIDGELINE
  at 18.06 s, meaning `Migration moving telemetry to a new cluster`, source `llm`,
  confidence `0.6`, suggested contact `Dana O.` / `Reliability` (not confirmed owner).
- Result: live typed-text backend inference passed. No email was sent. The real app
  DB still contains zero Ridgeline terms, so Sohail's next device test remains fresh.
  Physical G2 output and real-audio Ridgeline inference remain untested after this fix.

### 2026-10-17 — Agent prep and local UI presentation

- Pulled `origin/main` through `37a2b42` before this work. Agent prep was committed
  locally on `main` as `32c333f`; presentation work is on `kartik/paper-ui`.
- The agent now answers `Prep me for my 2pm platform sync` with five glossary
  entries from `data/company_pack.json`: 2pm platform sync (Ben Carter), FCS
  (Marcus Lindqvist), golden path (Tomas Reyes), Bluebird (Priya Raman), and
  DRI (Ben Carter). Each reply includes the pack meaning and team.
- Real ASI:One mailbox chat against the running local agent and backend:
  https://asi1.ai/shared-chat/5242abb1-e546-46d2-ad8c-8a2b2600a1a8
  It contains the prep request and both digest questions, in addition to the
  original Bluebird lookup. `What did I learn today?` returned HAL-9, runbook,
  FCS, and Bluebird; `Who should I meet?` returned Priya Raman, Marcus Lindqvist,
  and Dana Okafor. These matched the local `GET /digest` contents at the check.
- Public agent submission links: Agentverse profile
  https://agentverse.ai/agents/details/agent1qg8amcyx59uvzkpj3zyy260cd790ewlf0nuga3qydevs25489lv3vgvx4gq/profile
  and ASI:One profile
  https://asi1.ai/ai/agent1qg8amcyx59uvzkpj3zyy260cd790ewlf0nuga3qydevs25489lv3vgvx4gq
- Agent lookups read the pack directly; digest questions call only `GET /digest`.
  No glossary query calls `/listen_text`. No agent draft sending or backend API
  addition was implemented, so the frozen API contract is unchanged.
- The G2 renderer has explicit listening, term, queued, ready/empty, and error
  states within 576 × 288. The phone companion and digest initially shared a
  dark green presentation, revised in the field notes design below. SDK bridge,
  gestures, audio, API calls, and meeting
  transitions remain in their existing modules. `BACKEND_URL` stays localhost.
- Local verification: six agent tests; 21 client tests; TypeScript checks for
  both clients; production builds for glasses and web. These do not replace a
  physical G2 test. Screenshots are in `design/evidence/` (`phone-before.png`,
  `phone-after.png`, `phone-card-after.png`, `phone-queued-after.png`,
  `digest-before.png`, `digest-after.png`). The G2 layout source is in
  `design/g2-frames.html`.
- Editable Paper file: https://app.paper.design/file/01M56GD0RYAQWQJM4X2MFXNWRR/p-1-0
  It contains five 576 × 288 artboards named Listening, Term, Queued, Empty
  and ready, and Error. Reviewed exports are `paper-listening.jpg`,
  `paper-term.jpg`, `paper-queued.jpg`, `paper-ready.jpg`, and
  `paper-error.jpg` in `design/evidence/`.
- Local client settings are `MOCK_MODE=false` and
  `BACKEND_URL=http://localhost:8000` in ignored `.env.local` files for both
  clients. The optional StepFun intent router was deferred; the current
  keyword router handled all verified live questions. No deployment was
  performed. Sohail continues Ridgeline/“Line” and TLS work.

### 2026-10-17 — Cached-fragment fix and model comparison

- Later G2 feedback was a standalone LINE card, not verified full RIDGELINE output.
  The app DB contained an older generic LINE inference. Now exclude generic
  non-code LLM entries from matching and pending-card delivery, using the same
  check as new inference. Keep their existing queue, drafts and history intact.
  Full names and contextual meanings remain eligible; letter-number codes retain
  their cautious fallback. No term-specific substitution was added.
- Verification: 76 backend tests pass, including six old-cache/history cases;
  one existing Starlette/httpx deprecation warning remains. Backend restarted
  on port 8000. No database reset or email send; a read-only before/after hash
  confirmed queued work and drafts were unchanged during the live API diagnostic.
- Actual port-8000 diagnostic: a fresh Cedar Point phrase produced one candidate,
  but StepFun hit the 25 s cap with zero added cards. Health and OPTIONS passed.
  DNS cache reload did not permanently solve the earlier intermittent TLS errors.
  No TLS bypass or saved DNS change was made.
- With Sohail's permission, compared models in isolated synthetic calls, keeping
  the full company pack, low reasoning and JSON schema. Existing prompt:
  Step 5 Preview timed out after 35 s; 3.7 Flash returned a Ridgeline meaning in
  12.95 s; 3.5 Flash 2603 returned one in 30.55 s. These are individual samples.
- Shorter prompt: Step 5 returned a meaning in 30.68 s. A 3.78 s 3.7 Flash result
  rejected Ridgeline, so it is not a successful fast-card result. Restoring the
  absent-from-pack project rule gave full-name meanings for Ridgeline in 8.49 s
  and Cedar Point in 15.01 s, with suggested contacts at confidence 0.6.
- Successful TLS setup took under a second in these comparisons; waiting for
  response headers dominated. Completed benchmark calls cost approximately $0.02
  from reported token usage and official rates; timed-out usage was unavailable.
  App model and prompt remain unchanged. No model switch or new G2 latency is
  verified; the plan still requires runtime Step-5 Preview use for the prize.

### 2026-10-17 — Meeting Fieldnotes design and code

- Merged Sohail's latest `origin/main` commit `4e18db4` into `kartik/paper-ui`.
  His cached-fragment backend fix and its notes above are preserved. No backend
  API or endpoint was changed by the design work.
- Editable Paper file: https://app.paper.design/file/01M56HH1VJ2BSH57HAFMAF1RED/p-1-0
  Its first page compares three directions; Field notes was chosen. The next
  pages contain three 390 × 844 phone states and desktop/mobile digest frames.
  Tokens, type roles, interaction hierarchy and review images are documented
  in `design/FIELDNOTES.md`.
- The phone now puts Start listening and current G2 context first, reveals card
  actions only when a term exists, keeps End meeting accessible, numbers saved
  questions, and puts draft approval at the top after ending. The digest now
  reads like a ruled meeting ledger, with a focused G2 memory strip. Both use
  cool paper, spruce ink, square controls and restrained copy.
- G2 keeps the existing three containers and single event capture at 576 × 288.
  Brightness values were initially status 6, term 15, detail 11; the installed
  SDK rejects those values (see the correction below). The browser's G2 preview
  is conceptual; the firmware font cannot be
  replaced with the preview's font. Physical device fit/brightness still needs
  an on-device check.
- Before/after evidence is in `design/evidence/`: the baseline
  `phone-before.png` / `digest-before.png`, the Paper exports named
  `paper-directions.jpg`, `paper-phone-*.jpg`, `paper-digest-*.jpg`, and the
  local implementation screenshots named `phone-fieldnotes-*.jpg` and
  `digest-fieldnotes-*.jpg`.
- In local demo mode, the phone completed Start listening → Bluebird card →
  save question → End meeting → draft review without sending email. Desktop
  and mobile digest screenshots were checked. All 21 glasses/client tests and
  both TypeScript checks pass. After the merge, 76 backend tests and both
  production client builds pass. The backend test run reports the existing
  Starlette/httpx deprecation warning.
- This is local work only. Client `BACKEND_URL` remains
  `http://localhost:8000`; no deployment was performed.

### 2026-10-17 — G2 startup brightness correction

- Sohail reported startup failure while the glasses were paired. Reproduced the
  rejection with the installed SDK validator: `INVALID_TEXT_BRIGHTNESS`, status
  `textColor=6`; valid brightness is integer 0–4, not 0–15. Corrected the three
  containers to status 2, term 4, detail 3, preserving the new layout and text.
- Added an SDK-validation regression test for the actual startup-page payload;
  it failed before the correction. Updated the existing layout expectation.
- Verification: all 22 client tests and both production client builds pass.
- Restarted backend and both Vite servers. The user-supplied new tunnel passed
  health (200) and listen preflight (204 with CORS). Vite serves the new ignored
  glasses env; web remains on localhost. No meeting data was reset or email sent.
- Physical G2 reopening and visual confirmation remain pending Sohail's test.

### 2026-10-17 — Sohail's local agent environment

- Sohail created a separate local agent identity and registered its mailbox.
  Its address differs from Kartik's existing profile, so do not reuse the older
  profile/chat URLs to test this process. The seed remains in ignored `agent/.env`.
- Local API root returned 404 as expected; `/agent_info` returned 200. Opened the
  SDK's full Agentverse Inspector link in Chrome and confirmed the local agent.
- ASI:One questions reached the old process, but reply resolution and mailbox
  polling failed with `Can not decode content-encoding: br`. Reproduced the exact
  decoder TypeError in Conda Python 3.13.9: `aiohttp 3.14.3` with `brotlicffi 1.0.9.2`.
- Created ignored `agent/.venv` using Python 3.11.15 and installed the declared
  requirements plus pytest. All six agent tests pass. Restarted with the existing
  env; confirmed its fingerprint and registered address were unchanged. Logs show
  active registration, published chat manifest and mailbox registration success.
- No agent application code or global Conda package was changed. The agent uses
  the same local backend as Sohail's G2. Fresh ASI:One reply verification is pending.

### 2026-10-17 — Live agent reply and ASI mention parsing

- Sohail confirmed the local agent replied correctly to Bluebird in ASI:One.
- Ridgeline returned only help. Cached incoming payloads showed ASI:One prefixes
  `@agent...` before the question, causing the anchored unknown-term parser to
  miss it. Strip that leading address before routing; cover spaces and newlines
  through the real chat handler. Seven agent tests and both subtests pass.
- Ridgeline is absent from the company pack and current local digest. Term
  lookups remain glossary-only and read-only; they do not trigger inference or
  add sightings. Expected reply is a clear missing-glossary message. Restarted
  the same local identity with the fix; its new live Ridgeline reply is unverified.

### 2026-10-17 — Agent reads learned meeting definitions

- Sohail expects the agent to reuse definitions learned during G2 meetings.
  Keep direct company-pack lookup first, then check existing read-only `GET /digest`
  for a matching recent term. Label model meanings as inferred and their people
  as suggested contacts. No API paths/shapes changed, no lookup calls `/listen_text`,
  and unknown names are not invented or silently matched to a different project.
- Ten agent tests and both subtests pass, including glossary priority, inferred
  contact labeling, backend failure and distinct Red Line/Ridgeline names. Restarted
  the existing agent identity. Live local-backend reads answered Pinecrest and
  Red Line; a before/after check confirmed sighting state was unchanged.
- The current store has Red Line and Pinecrest, but no Ridgeline. One explicit
  typed-meeting rehearsal for Ridgeline hit the existing 25 s StepFun cap:
  `llm_ms=25002 candidate_count=1 added_count=0`. Ended that test meeting with
  zero drafts and confirmed existing queue/drafts were unchanged.
- Sohail confirmed Red Line was a transcription error and authorized correcting
  the saved name to Ridgeline. Changed only that term's display name, keeping its
  ID, meaning, contact and source. Transaction assertions confirmed all sightings,
  queues and drafts were unchanged; the already-sent email still says Red Line.
- Restarted the backend to refresh its matcher. Verified a mention-prefixed
  Ridgeline lookup against the live local digest returns `Telemetry migration to
  the new cluster`, labeled inferred, with Marcus Lindqvist (Platform) as suggested
  contact. Lookup did not change sightings. The agent remains active with its
  existing identity; the updated ASI:One reply still needs Sohail's confirmation.

### 2026-10-17 — Private agent identity and profile replacement

- Sohail confirmed the correct Ridgeline answer in ASI:One on the previous agent.
  Native ASI:One mobile-app availability remains unverified.
- Found that the running local identity used the public example seed. This
  corrects the earlier assumption that its seed was private. Sohail authorized
  replacement; generated a new 256-bit random seed in ignored `agent/.env`, with
  file permissions 0600. Kept other env settings unchanged; no secret is in this file.
- Registered the replacement through Agentverse's identity challenge and API,
  preserving the current README, both badges and Agent Chat Protocol. Verified
  the name **Footnote Jargon Decoder**, handle `footnote-jargon-decoder`, and the
  description covering jargon, learned terms, meeting prep and suggested contacts.
- Moved the handle to the new identity. The previous profile is marked
  **Footnote (retired)** with a distinct retired handle; its old chats were not deleted.
- Stopped the previous process and started the replacement locally on port 8001.
  Confirmed saved seed matches `/agent_info`, chat manifest publication, public
  Almanac status `active`, and a mailbox endpoint. Bluebird and Ridgeline local
  read-only answers are correct. Fresh ASI:One verification is recorded below.
- Added a startup guard rejecting the public example seed; its regression test
  failed before the fix. All 11 agent tests and both subtests pass.
- Verified authenticated mailbox reads return 200. A signed synthetic chat
  acknowledgement sent through the public mailbox endpoint was retrieved by the
  running agent and appeared in its local message history. This tests transport,
  not a fresh ASI:One conversation; no other recipient was contacted.
- Current Agentverse profile:
  https://agentverse.ai/agents/details/agent1qtm5jg9yr7e35ysxxahsvwc84g2yx95dkljesugg9xvdwmy8lp655tm2u2r/profile
- Current ASI:One page (a new chat, not yet a public shared-chat submission link):
  https://asi1.ai/ai/agent1qtm5jg9yr7e35ysxxahsvwc84g2yx95dkljesugg9xvdwmy8lp655tm2u2r
- Keep the local agent running. Do not overwrite its env or restore the example
  seed. No backend/data/client code, deployment, email or Git commit was changed here.

### 2026-10-17 — Replacement agent verified in ASI:One

- Sohail supplied a screenshot showing the replacement address replying in
  ASI:One with the correct display name and `@footnote-jargon-decoder` handle.
- Verified in that conversation: Bluebird meaning and Priya Raman (Autonomy);
  Ridgeline meaning labeled inferred with Marcus Lindqvist (Platform) suggested;
  `Who should I meet?`; `What did I learn today?`; and the help response.
- Sohail retested the replacement in the native ASI:One phone app; it still
  reports that the agent is unavailable in the mobile app. Native-app testing
  is blocked by current platform support: Sohail checked directly with the
  Fetch.ai team, who confirmed third-party agents are not yet available in the
  native mobile app and that working on ASI:One web is sufficient. This is
  team guidance relayed by Sohail, not an independently verified public policy.
  No Footnote mobile compatibility fix is required for the current submission.
- The replacement's public shared-chat submission URL is recorded at the top
  and in the shared-chat entry below; it is separate from the ASI:One agent page.
- Local mention-prefixed `Prep me for my 2pm platform sync` returns five glossary
  entries with meanings and owners: 2pm platform sync, FCS, golden path, Bluebird,
  and DRI. This is a fixed selection from the company pack, not calendar/agenda
  inference. Sohail then supplied a screenshot confirming ASI:One delivers all five
  entries with the expected meanings and owners on the replacement identity.
  Native-app access is unsupported per the Fetch.ai team guidance above.
  Phone-browser access remains untested; it is optional for the current submission.

### 2026-10-17 — Pulled Kartik's Afterimage UI

- Fast-forwarded main to `64133b6`; restored all local agent work and merged both
  handoff updates without conflicts. All four local env files are unchanged.
- Verified 24 client tests, 79 backend tests, 11 agent tests plus both subtests,
  and both production client builds. Backend retains its existing dependency warning.
- Restarted the backend for Discard support; verified its additive migration
  preserves all existing database rows. Health, CORS preflight, Discard route,
  both Vite servers and agent-to-backend Ridgeline lookup pass. No reset or email.
- Sohail subsequently confirmed the UI test flow works on physical G2 and phone;
  see the UI confirmation entry below.

### 2026-10-17 — Current public shared-chat submission link

- Sohail created and supplied:
  https://asi1.ai/shared-chat/c130fcb3-8bf2-4d92-b88f-e8d17cf1c777
- Anonymous HTTPS request, without cookies or an authorization header, returned
  200 at that same URL with title `Meaning Of Bluebird At Halcyon` and matching
  canonical shared-chat URL. This confirms public page reachability.
- The page loads messages through JavaScript. The automated check confirmed
  reachability only; Sohail subsequently opened the shared link in an incognito
  window and confirmed everything is visible properly. Signed-out message
  visibility passes based on Sohail's browser check. The live replies themselves
  were also verified earlier through his screenshots.
- Pair this link with the current Agentverse profile above for the Fetch
  submission; older shared-chat links in this changelog are historical.

### 2026-10-17 — Sohail confirms updated UI

- After testing the updated UI, Sohail reported: `Yes everything works`.
  The requested checks covered G2 border, text spacing and contact line; phrases
  for cutover, brownout, wave planning / 2pm platform sync and Atlas; saving a
  question, ending the meeting, and phone draft Discard / Undo.
- Treat this as Sohail's device-test confirmation, not an independently observed
  run or measured latency result. Sohail also confirmed full shared-chat message
  visibility in incognito, as recorded above. No further code change was made here.

### 2026-10-18 — Personalized agent meeting prep

- Replaced the fixed prep response with agenda-based prep in `/agent`. It reads
  the company pack and read-only `GET /digest`, shortlists relevant candidates,
  and uses StepFun `step-5-preview` to select up to five saved term IDs and propose
  three questions. Meanings and contacts are rendered from the original records;
  glossary facts take precedence, and learned inferences stay labeled inferred
  with suggested contacts. Questions are suggestions only; nothing is sent.
- Added optional `STEPFUN_API_KEY` to the agent env example and configured it in
  the ignored local agent env. The seed and all other env settings are unchanged.
  No new dependency or backend API change. Backend, data and client code untouched.
- Verified all 20 agent tests plus 19 subtests, covering distinct agendas,
  learned terms, malformed history/model replies, model timeouts, glossary
  precedence, fallback, and mention-prefixed ACP handling with acknowledgement.
- Live checks called the actual chat handler locally with a test reply context,
  the running backend and real StepFun. This tests reply generation and ACK order,
  not delivery through ASI:One. Both final checks passed:
  - Telemetry review about Ridgeline and FCS: selected those two terms;
    `llm_ms=18348`, total 18357 ms. Ridgeline kept its inferred meaning/contact.
  - Incident review about SLO and runbook: selected SLO, runbook and postmortem;
    `llm_ms=33155`, total 33162 ms. Each brief included three proposed questions.
- Compared all rows in all seven backend tables before/after the final live
  checks: unchanged. No sightings, queues, drafts or emails were created.
- Earlier full-pack trials triggered model-response validation fallback and timeouts.
  The final version shortlists up to 12 keyword-relevant candidates, allows a
  4096-token response budget, and has a 45-second agent-only model timeout.
  Missing key, timeout or invalid plan returns a labeled keyword brief with
  three template questions; missing history falls back to the glossary.
  This does not change the phone's six-second listen timeout. Latency varies.
- Local runtime uses the same registered identity on port 8001. Sohail's
  ASI:One web retest passed, as recorded below. The public shared chat showing
  the new flow and its verification are recorded below. The updated local README is ready for the
  Agentverse Overview; public profile text refresh has not been verified.
  Deployment and Beta remain untested.

### 2026-10-18 — Sohail verifies personalized prep in ASI:One

- Sohail pasted both complete web replies from `@footnote-jargon-decoder`,
  timestamped 12:32 AM and 12:33 AM. Both were labeled **StepFun selection;
  definitions from saved records** and contained three agenda-specific questions.
- Telemetry prep returned Ridgeline and FCS. Ridgeline retained its inferred
  meeting definition and Marcus Lindqvist (Platform) as a suggested contact;
  FCS retained its glossary definition, owner and recent-meeting label.
- Incident prep returned SLO, runbook and postmortem with their saved meanings
  and Dana Okafor (Reliability) as owner/contact. Its questions differed from
  the telemetry brief and addressed incident review and postmortem preparation.
- Personalized prep delivery through ASI:One web passes based on Sohail's
  supplied conversation. These timestamps are not a measured latency result.
  The new shared-chat link and subsequent visibility check are recorded below;
  the earlier incognito check covered the previous conversation contents.

### 2026-10-18 — Public personalized-prep demo chat

- Sohail supplied the new demo link:
  https://asi1.ai/shared-chat/886cf7a4-bd67-49f6-a14c-34ecbf9bcf07
- An anonymous HTTPS request without cookies or an authorization header returned
  200 at the same URL, with title `Telemetry And Incident Review Prep`. Message
  text is loaded through JavaScript and was absent from the initial HTML;
  the automated check verifies page reachability only.
- After being asked to check the updated conversation in incognito, Sohail
  confirmed: `I checked and it works`. Message visibility passes based on his
  browser check, alongside the complete live replies he supplied above.
- Use this link as the current Fetch demo chat. The previous shared link remains
  in the historical entries; the current agent identity/profile is unchanged.

### 2026-10-18 — Railway backend, agent and digest deployment

- Deployed three services from the repo root: existing `backend/Dockerfile`,
  new `agent/Dockerfile`, and new `web/Dockerfile`. Added
  `docs/railway-deployment.md`, Docker context exclusions for private/runtime
  files, and README/setup links. No backend, data, client UI or API contract change.
- Backend uses one replica/worker, a persistent volume at `/var/data`,
  `DB_PATH=/var/data/footnote.db`, and `ENABLE_DEBUG_RESET=0`. Secrets are Railway
  variables; no real values or deployment URLs belong in Git.
- Imported a consistent SQLite backup: 12 people, 42 terms, 5 sessions, 9 seen
  rows, 12 cards, 11 queued questions and 9 drafts. Uploaded to a separate unopened
  database, downloaded it again, and verified byte equality and SQLite integrity
  before switching the running service to it. All nine learned digest terms,
  including Ridgeline, matched the local snapshot.
- HTTPS checks passed: `/health` 200, `OPTIONS /listen` 204 with CORS, public
  `/debug/reset` 404. Typed API rehearsal using exact client request shapes passed:
  start -> BOM + NRE cards -> queue BOM -> mute NRE -> end -> Hana draft -> digest.
  Listen HTTP round trip was 314 ms; this is not speech or G2 latency.
  Draft signature was Sohail. No send request was made and no cloud email is verified.
- Confirmed a fresh backend startup in Railway logs after restart, then compared
  the entire digest with the pre-restart response: unchanged, including the two
  rehearsal terms. Active in-memory sessions do not survive a restart.
- Stopped the local agent before deploying the same private identity on Railway.
  Cloud logs confirmed protocol publication and active mailbox registration.
  Inside the actual cloud container, read-only Bluebird and Ridgeline lookups
  passed; personalized telemetry prep used the deployed backend and live StepFun:
  `llm_ms=17716`, total generation 17739 ms, two terms and three questions.
  This is handler generation, not a fresh ASI:One delivery test. A separate public
  Almanac HTTP check returned 403; it did not independently verify registration.
- The digest's Railway Docker build passed. Its HTTPS HTML, JS and CSS returned
  200; JavaScript contains the live backend origin, excludes demo mode and private
  env values. Web-origin listen preflight passed; live digest includes Ridgeline.
  Browser rendering still needs Sohail's check.
- Fresh local checks: backend 79 tests; agent 20 tests plus 19 subtests; client
  24 tests; web production build. All passed, with the existing backend dependency
  deprecation warning. Real audio on Railway, cloud G2 flow, cloud email, new
  ASI:One delivery and live Beta build/upload/install remain untested.
- Local client/backend env files remain on their prior development settings.
  Use the hosted backend origin when building the live Beta. Public service URLs
  are shared privately; the stable agent profile/shared-chat links above still apply.
- Removed the temporary Railway SSH credential and its local key files, then
  stopped its isolated SSH agent. The protected local SQLite backup is retained
  for recovery. Unrelated local skills files were left untouched.

### 2026-10-18 — Hosted UI check and readable agent mentions

- Sohail reports the hosted dashboard link works. Its browser check is
  user-reported; no automated visual inspection was performed.
- A fresh ASI:One question reached the Railway agent and received help instead
  of the learned Ridgeline definition. Reproduced with the exact readable-handle
  prefix: routing stripped `@agent1...` addresses but not `@footnote-jargon-decoder`.
  The same question without a prefix or with an address returned the right answer.
- Generalized the existing leading-mention removal in `agent/footnote.py` to
  handles containing word characters, hyphens or dots. Added ACP regression cases
  for handles, newlines and learned definitions. All four new cases failed before
  the fix; the full agent suite now passes: 21 tests plus 23 subtests.
- The actual corrected chat handler, run locally against the live Railway
  digest, acknowledged the exact question and returned the saved Ridgeline meaning,
  inferred label and Marcus Lindqvist (Platform) as suggested contact. The digest
  was unchanged. This verifies generation; a fresh ASI:One retest after deployment
  is still required.
- Redeployed the agent fix to Railway successfully. Fresh startup logs show the
  same registered address, active registration and published Agent Chat Protocol.
- The hosted `web` service is the post-meeting digest. The main phone/G2 UI is
  `glasses/`; the current QR loads it from the laptop. The live Beta `.ehpk` will
  bundle that UI and its backend origin. Packaging, upload and installation are
  still pending; no hosted phone UI service was created.

### 2026-10-18 — Live Beta built and Sohail confirms device flow

- Pushed deployment setup and the agent mention fix as `de78f0b`, then ignored
  root `.claude/` and `skills-lock.json` in `2c23bf4`. No secret or deployment URL
  was committed. The ignored glasses env now uses the hosted backend with mock
  mode off; the local web env was left unchanged.
- `npm run pack` passed and produced `glasses/footnote.ehpk` (46,886 bytes),
  version `0.1.0`, SDK `0.0.16`, minimum phone app `2.2.10`. Build checks confirmed
  live mode, the sole backend-origin network whitelist, microphone permission,
  and no provider keys, seed, inbox, localhost or tunnel URL in the build output.
  Artifact SHA-256:
  `bcfd7844ebfac9709ac245e5889cb46c881fc416a21e8b8bdc4d0150d33d336d`.
- Guided the Even Hub Beta group/build assignment and phone installation. After
  receiving typed-then-spoken test phrases and the queue-to-email sequence,
  Sohail reported: `Done everything works as expected`. Record the installed
  Beta's requested card, queue, mute, end, draft approval and email flow as
  user-confirmed, not an independently observed run or provider delivery audit.
- Requested glossary pairs: SLO/runbook, Kestrel/freeze window, SLAM/shadow mode,
  rev B/e-stop, Beacon/BRT, RFC/DRI. The fresh inference phrase was
  `The Cedar Point migration moves our telemetry onto the new cluster.`
  His overall confirmation covers this requested test; no exact StepFun reply
  or measured cloud/G2 latency was supplied, so do not invent either.
- Still untested on this Beta: five-minute phone lock, microphone denial,
  system-exit confirmation/cancellation, and launching a native app after exit.
  A fresh ASI:One retest after the readable-handle fix remains separately pending.
  Demo video and Devpost/sponsor submission remain to be completed.

### 2026-10-18 — ASI follow-up extension local verification

- Added only a protected read endpoint and agent-side review/approval orchestration.
  The contract addition is recorded at this file's top and in CLAUDE.md. Existing
  send/discard behavior, fixed demo inbox, database schema and G2 Beta are unchanged.
- Local backend: 85 tests pass; agent: 43 tests plus 23 subtests pass. New tests
  failed before implementation. Existing backend deprecation warning remains.
- Actual HTTP integration used a temporary SQLite backend and simulated mailer:
  old typed cards -> queue -> mute -> end -> ACP acknowledgement/preview -> reject
  another conversation's code -> simulated provider failure -> explicit retry ->
  exactly one simulated send -> digest. No real email or provider key was used.
- Fresh independent code review found no important/critical defects. Real ASI:One
  must still verify session binding and actual delivery after deployment. This
  is a shared single-user synthetic demo, not multi-tenant authorization.
- Updated server env examples, runtime Docker COPY, operator instructions and
  agent listing. Both Devpost and the Fetch Submission Agent are required.
