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
2. **Deploy backend to public HTTPS.** Use `backend/Dockerfile`, building from the
   repo root: `docker build -f backend/Dockerfile -t footnote-backend .`.
   Set the four required backend variables as host secrets. Verify deployed
   `/health` and an `OPTIONS /listen` preflight with origin/method/content-type
   headers; expect 200 and 204 respectively with CORS headers. Post the deployed
   URL in our private chat, never in this repo. Record deployment/check outcomes
   here without exposing the URL or secrets. Container build/deploy is untested.
3. **Set `NEW_HIRE_NAME=Sohail`** in the ignored backend env and deployment env;
   restart as needed and verify the intended draft signature. This is untested.
4. **Measure real-audio backend timings.** POST a real speech recording as raw
   16 kHz, signed 16-bit little-endian mono PCM to `/listen?session_id=...`.
   Normal chunks are 128,000 bytes (4 seconds). Record actual `stt_ms`, `match_ms`
   and `llm_ms` log lines and the returned cards; distinguish background inference
   from the immediate response. Target card-on-glasses time is about 4 seconds.
   Backend timings alone do not prove that target; G2 latency remains untested
   until Sohail measures it. Do not invent measurements from the chunk duration.
5. **Stretch only after 1-4:** implement the Fetch.ai agent in `/agent` per PDF K7.
   Registration, ASI:One chat and deployment are all untested.

## Rules while Sohail sleeps

- You own `/backend`, `/data`, `/agent`. Keep changes there by default.
- Fix `/glasses` or `/web` only for a client bug blocking tasks 1-2. Use branch
  `kartik/client-fix`, keep the diff minimal, and list EVERY changed file and
  behavior in the changelog below for Sohail to review. Do not merge it silently.
- Keep API paths/shapes frozen in `CLAUDE.md`; document any change at this file's top.
- Never commit real env files, keys, tunnel/deployment URLs, inbox addresses or LAN IPs.
- Record failed checks and provider errors honestly. Preserve drafts on send errors.

## Sohail after the nap

- Test queue -> end -> draft -> approve -> email, inbox/spam, and remaining gestures
  on real G2, including fade-out. These device checks are still untested.
- With the deployed URL, build a live `glasses/footnote.ehpk`, upload/install Beta
  and retest. This distribution path remains untested.
- Update README "Run on G2" using only observed results, then demo video and Devpost.

## Changelog for Kartik's agent

Append dated entries with task, files/branch, exact checks and results, sanitized
log timings, failures, outstanding work and any contract changes. No work by
Kartik's agent is recorded yet. Do not mark an unrun check as passed.
