# Sohail implementation checklist

Source: `Footnote LA Hacks 2026 Build Plan.pdf`, Sohail prompts S1–S6,
and the frozen API in `CLAUDE.md`. Implement inline in this session.

Architecture: official ASR starter adapted into a thin Vite/TypeScript
glasses client and one framework-free phone page. All model calls, state
authority, fade-out, and email delivery belong to Kartik's backend.
React/Vite digest uses the same REST client. No provider keys enter bundles.

- [x] S1: three text containers, exact IDs/names/coordinates and brightness;
  startup before microphone; explicit two-card mock; simulator.
- [x] S2: gestures, omitted-zero click routing, 8-second expiry, 2-second
  queue confirmation, next/replay, mute, end, system exit confirmation.
- [x] S3 client code: 128,000-byte PCM chunks, 6-second timeout, bounded upload queue,
  partial final chunk, lifecycle pause, failure state, typed fallback.
- [x] S4: start/pause/end, current card, queued questions, draft approval
  with individual send state; safe text rendering and duplicate-action guard.
- [x] S5 local packaging: reproducible pack command with installed SDK version, manifest
  whitelist generated from BACKEND_URL, live and clearly named demo packages.
- [x] S6: responsive green-on-dark digest with loading, empty, error and retry.
- [x] Env examples, root scripts, lockfile and Run on G2 guide.
- [x] Tests: PCM integrity, event envelopes, contract and timeout, mock
  fade-out, failed actions, stale audio results, explicit approval.
- [x] Build both apps, browser demo flow, simulator render and CLI packaging.
- [ ] Real-device S3 check: spoken Bluebird reaches the glasses through the deployed backend.
- [ ] S4/S6 live integration with Kartik's deployed backend and real demo email.
- [ ] S5 Beta portal upload, phone installation and real-device retest.

Local verification: 18 Node tests pass. Both mock and live configurations
compile. Browser tests completed mock and intercepted-live approval flows
without runtime errors; draft markup remained text and no send preceded
approval. Mobile views have no horizontal overflow. The official simulator
rendered the Bluebird card and queue confirmation. The CLI produced
`glasses/footnote-demo.ehpk` against SDK 0.0.16 / app floor 2.2.10.

Review focus: audio must never act as a tap; backgrounding stops capture;
failed end keeps the session retryable; late uploads cannot repopulate an
ended meeting; duplicate presses cannot send/queue twice during an action.

Visual direction: pine #10251d, charcoal #0c120f, mint #b8f4bf, off-white
#edf4ee, muted sage #9baa9e, border #30463a. System humanist sans for phone
controls and digest; monospace only in the faithful 576×288 glasses preview.
Left aligned, generous touch targets, one clear active card and simple lists.
No font downloads, decorative motion, or framework for the phone page.

Hardware/account checks cannot be replaced by mock checks: actual G2 mic,
glyphs, lock recovery, denied permissions, QR pairing, Beta install and email
delivery must be verified after real configuration. Paper design is a
separate stretch requiring Paper Desktop; do not claim Paper usage.
