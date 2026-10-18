# ASI:One approved follow-ups implementation plan

> **For agentic workers:** Implement inline using superpowers:executing-plans; test each task before deployment.

**Goal:** Review the latest ended meeting's pending drafts and explicitly approve one email inside ASI:One.
**Architecture:** Add a token-protected, read-only backend endpoint. Keep existing send behavior. The agent owns short-lived, conversation-bound approval codes and never treats LLM output as permission to send.
**Tech Stack:** Existing Python 3.11, FastAPI, SQLite, uAgents and standard library; no dependencies.
**Spec:** User-approved workflow in this conversation: preview recipients/subject/body, approve one draft, cancel without sending, preserve failures and duplicate-send protection, preserve deployed G2 behavior.

## Global constraints
- Existing endpoint paths/shapes and the installed G2 Beta remain unchanged.
- Document the additive contract at the handoff top and in CLAUDE.md before app changes.
- No schema migration, reset, seed replacement or new email recipient. Delivery remains DEMO_INBOX only.
- AGENT_API_TOKEN is server-only; endpoint is disabled when absent and rejects incorrect bearer tokens.
- Preview only the latest ended meeting, excluding sent/discarded drafts; never fall back silently to older meetings.
- Explicit Approve <code>, bound to sender and conversation, expires after 10 minutes. Cancel clears approval only.
- Retain the same draft ID on retries; no automatic send retries. Clearly report uncertain outcomes.

## Review focus
- Missing/wrong token exposes no draft content.
- Another sender/conversation, generic yes, malformed or expired code cannot send.
- New preview invalidates old approval codes; restart requires preview again.
- Phone-side send/discard and network failures retain existing backend behavior.
- Existing glossary/prep/chat acknowledgement and G2 API flow continue working.

## Task 1: Protected pending-draft read
Files: backend/app/db.py, backend/app/main.py, backend/tests/test_agent_followups.py, backend/tests/conftest.py, CLAUDE.md, docs/handoff-for-kartik.md.
Produces: GET /agent/drafts/pending -> {session_id: string|null, drafts: Draft[]} with Bearer AGENT_API_TOKEN.
- [x] Write tests for disabled/wrong authentication, latest ended meeting selection, sent/discard exclusions, empty latest meeting and read-only behavior.
- [x] Run tests and observe failures, then implement Store.pending_agent_drafts() and protected route.
- [x] Run full backend suite; expected all pass with only existing dependency warning.

## Task 2: ASI preview/approve/cancel
Files: agent/followups.py, agent/agent.py, agent/tests/test_followups.py, agent/tests/test_chat_protocol.py, agent/Dockerfile, agent/.env.example.
Consumes the new GET response; sends via existing POST /drafts/{id}/send.
Produces: Followups.reply(query, sender, conversation) -> str|None, called before existing answer_text.
- [x] Write failing tests covering preview-only, exact approval, cancellation, sender/conversation binding, expiry, duplicate approvals, provider/network failures and malformed data.
- [x] Implement bounded in-memory review state, standard-library HTTP and deterministic commands; missing configuration fails closed.
- [x] Verify real ACP handler acknowledges before tool execution and preserves old answers. Run full agent and client suites.

## Task 3: Deploy and verify
Files: docs/railway-deployment.md, agent/SETUP.md, agent/README.md, README.md and handoff.
- [x] Fresh whole-change review; fix important issues with regression tests.
- [x] Retain known-good Railway deployment IDs and consistent volume configuration. Set shared token privately.
- [x] Deploy backend first, then verify health, CORS, digest preservation and old typed flow before agent deploy.
- [x] Deploy agent with the same seed, then verify ASI preview -> explicit approval -> one delivered demo email with Sohail. Do not send automated diagnostic emails.
- [x] Record actual evidence and outstanding checks; keep inbox and secrets out of Git. G2 artifact hash must remain unchanged. Sohail subsequently authorized public production links in the README for submission.

Acceptance: Sohail confirmed email receipt after releasing USC Proofpoint quarantine.
Live ASI cancellation, expiry and duplicate approval remain untested; automated
coverage passed. Public action chat:
https://asi1.ai/shared-chat/3e91ca9e-4730-4f89-bf64-0c24467f87e1
Anonymous HTTP 200 passed; Sohail confirmed preview, approval and send confirmation
are visible in incognito. Inbox receipt was confirmed separately.
