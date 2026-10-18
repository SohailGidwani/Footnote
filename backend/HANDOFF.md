# Backend handoff for Sohail

The API paths and response shapes in `CLAUDE.md` are unchanged. The timing rule changed:
glossary cards still return in the current `/listen`, while an uncatalogued StepFun card
returns with the first `/listen` **after** inference finishes. The StepFun background cap is
25 seconds (raised from 12 after live Step-5 Preview calls took 15.7-16.5 seconds).
Do not wait for that card in the phone request; the existing
6-second phone timeout can stay as it is.

## Changes in this push

- Queueing a card now saves a template draft immediately and starts a StepFun draft in the
  background. More questions for the same owner refresh the template and restart drafting.
  `/session/{id}/end` freezes the latest saved draft and returns quickly; if StepFun is still
  running, it returns the template. Sending before end is rejected.
- The HAL-9 slow path now asks for a cautious explanation from meeting context even when a
  term is absent from the company pack. Inferred cards are limited to 0.7 confidence. If the
  model times out or gives malformed fields, a coded term tied to one named coworker and work
  context can show `Internal code; details unconfirmed` at 0.6 confidence. This is a generic
  cue to ask the owner, not a claimed definition.
- Session end and draft recovery are transactional and retryable. Sending uses the draft ID
  as Resend's idempotency key and still sends only to `DEMO_INBOX`.
- Pending cards take priority, shown cards stay shown across backend restarts, and the broad
  `the bake off` alias was removed. Silence detection, request limits, provider timeouts, and
  log privacy were tightened.
- Added a Dockerfile and build ignore rules. The root `env` and backend `.env` remain ignored.

## Verification and live checks

The offline backend suite passes with service keys blank. It covers the phone API contract,
prompt and HAL-9 fallback, draft timing and refresh, transaction rollback, and send retry.
No paid provider call or real email was made during these checks.

Before the demo, build the container from the repository root, deploy it at a public HTTPS
URL, and check `/health` and an `OPTIONS /listen` preflight. Then run one live meeting with
`STEPFUN_API_KEY` credit, verify a HAL-9 card appears on a later listen, queue questions,
end the meeting, and approve one email to `DEMO_INBOX`. Keep the service keys only in the
backend deployment's secret settings. Local Docker build was unavailable because the Docker
daemon was not running.
