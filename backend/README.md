# Footnote backend

FastAPI + SQLite. Implements the frozen API in the root `CLAUDE.md`. Every third-party call
(ElevenLabs, StepFun, Resend) happens here; no keys leave this folder.

## Run locally

```powershell
cd backend
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
# put real keys in backend/.env (copy names from the root .env.example); it is git-ignored
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`GET http://localhost:8000/health` returns `{"ok": true}`. Interactive docs: `/docs`.
Tests (offline, no keys needed): `.venv\Scripts\python.exe -m pytest -q`.

Without a key the matching feature degrades instead of failing: no `STEPFUN_API_KEY` means no
slow-path cards and template drafts; the glossary fast path and `/listen_text` always work.

## Behavior worth knowing

- **Fast path:** glossary match on the transcript, answered in the same `/listen` response
  (about 2 ms). At most 2 cards per call; pending cards take priority on the next response.
- **Slow path:** capitalized words and acronyms not in the glossary go to StepFun in the
  background, capped at 25 s. Its cards ride on the first `/listen` after the result is ready,
  and are cached as `source: "llm"` terms afterwards. Uncatalogued code meanings are hedged
  and have confidence at most 0.7. A coded term linked to one named coworker and work context
  can fall back to a generic, explicitly unconfirmed meaning if StepFun returns malformed data.
  For inferred terms, the listed contact is a suggested person to ask, not confirmed ownership.
- **Fade-out:** a term is issued at most once per meeting, including after a server restart;
  each issued card counts as one sighting.
  After 3 sightings, or a mute, it is never returned again.
- **Word-boundary overlap:** the last 400 ms of each audio chunk is prepended to the next so a
  term split across two chunks is still heard. All-zero chunks skip speech-to-text by default.
- **Drafts:** Queueing a question immediately saves a usable template per owner and starts
  StepFun in the background. More queued terms refresh that owner's template and restart the
  draft task. `/session/{id}/end` freezes the latest saved version and returns promptly, even
  if StepFun is still working. The end marker commits atomically and a failed end remains
  retryable. Sending is allowed only after end. `/drafts/{id}/send` sends via Resend to
  `DEMO_INBOX` only, using the draft ID as Resend's idempotency key. Company-pack emails are
  display-only.
- **CORS:** every response carries `Access-Control-Allow-Origin: *`; every `OPTIONS` preflight
  gets `204`.

## Optional environment variables

| Name | Default | Purpose |
|---|---|---|
| `ELEVENLABS_STT_MODEL` | `scribe_v1` | `scribe_v2` also works |
| `NEW_HIRE_NAME` | `Alex` | Signature on drafted messages |
| `ENABLE_DEBUG_RESET` | off | Set to `1` to enable `POST /debug/reset` (clears sightings and mutes between rehearsals) |
| `OVERLAP_MS` | `400` | Audio carried over between chunks |
| `SILENCE_PEAK` | `1` | Chunks quieter than this are not sent to speech-to-text |
| `DB_PATH` | `backend/footnote.db` | SQLite file (reseeded from `data/company_pack.json` on startup) |

## Container deploy

Build from the repository root so both `backend/` and `data/` are available:

```bash
docker build -f backend/Dockerfile -t footnote-backend .
```

The container listens on `PORT` (default `8000`) and stores SQLite in `/tmp/footnote.db`.
This is temporary storage; a restart clears meetings and sightings. Set the four backend keys
and `DEMO_INBOX` in the host's secret settings. Check `/health` and an `OPTIONS /listen`
preflight after the public HTTPS URL is live. The repository `.dockerignore` excludes local
secret files from the build context.

## Quick examples

```bash
curl -s -X POST localhost:8000/session/start                     # {"session_id":"s_..."}
curl -s -X POST localhost:8000/listen_text -H 'Content-Type: application/json' \
  -d '{"session_id":"s_...","text":"Bluebird is blocked on SOC2"}'
curl -s localhost:8000/digest
```
