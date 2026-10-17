# Footnote

A little context for your first week. Footnote listens during a meeting,
shows unfamiliar company terms and their owners on Even G2 glasses, and
lets you queue questions to send after the meeting.

This checkout implements Sohail's S1–S6 from the build plan:

- `glasses/`: TypeScript + Vite + Even SDK. Three text containers, gestures,
  16 kHz PCM upload, meeting controls, queued questions, and draft approval.
  The phone interface is in `glasses/src/main.ts`, without a UI framework.
- `web/`: React + Vite meeting digest: learned terms, people, sent messages.
- Kartik owns `backend/`, `agent/`, and `data/`. Those services are not
  implemented here. The clients use the frozen contract in `CLAUDE.md`.

## Local setup

Use Node **22.18+** (Node 24 LTS recommended) and npm. The SDK, CLI and
native desktop simulator are installed locally; no global install is needed.

```sh
npm ci
cp glasses/.env.example glasses/.env.local
cp web/.env.example web/.env.local
npm run dev
```

Open <http://localhost:5173>. The default is explicitly labeled **demo mode**;
it works without a backend or any keys and does not record or send email.
Start a meeting to get Bluebird and FCS. Queue Bluebird, advance to FCS,
mute it, end the meeting, then approve the draft. Find terms under
"Try a phrase instead" lets you try repeated sightings and fade-out.
Demo mute/seen state lasts until the page reloads.

In another terminal:

```sh
npm run dev:web
```

Open <http://localhost:5174>. The mock digest has independent sample data;
it does not synchronize with the mock phone page. Live mode reads `/digest`.

## Environment

Set these in **both** `glasses/.env.local` and `web/.env.local` when Kartik's
backend is ready:

```dotenv
BACKEND_URL=https://your-backend.example.com
MOCK_MODE=false
```

Use the backend **origin only**, without paths, queries, or credentials.
Restart Vite after changes. These public settings are compiled at build time;
rebuild and repack after changing them. `http://localhost:8000` is accepted
for laptop development, but a phone cannot reach your laptop through its
own localhost. Device packages require HTTPS.

The root [`.env.example`](.env.example) is a **server-only reference** for
Kartik: `ELEVENLABS_API_KEY`, `STEPFUN_API_KEY`, `RESEND_API_KEY`, `DEMO_INBOX`,
and the optional Fetch.ai keys. Copy it into `backend/.env` once that folder
exists. Do not put provider keys in the client env files. Neither client
calls a provider directly, and Vite exposes only the two public settings.

Every live backend endpoint must send CORS headers and answer OPTIONS
preflights as specified in `CLAUDE.md`. There is no automatic mock fallback
on network errors. Drafts send only after individual approval; a timed-out
send has an unknown outcome, so check the inbox/backend before retrying.

## Run on G2

1. Install the Even Realities phone app **2.2.10 or later**, sign into your
   Even account, and pair the G2. Permit the glasses microphone when prompted.
2. Run `npm run dev`, then `npm run simulate` in a second terminal to test
   the display locally. The simulator is included as a dev dependency.
   In demo mode Start injects the two mock cards and never starts the mic.
3. For real audio, use `MOCK_MODE=false` and a reachable HTTPS backend.
   Connect your phone and laptop to the same network or phone hotspot.
4. Generate the sideload QR with your laptop's LAN address:

   ```sh
   npm exec -w glasses -- evenhub qr --url http://YOUR_LAPTOP_LAN_IP:5173
   ```

5. Scan from the Even Realities app and open Footnote. The startup page
   must succeed before microphone capture starts. Press once or use Start
   meeting. Speak "Bluebird"; a live card requires Kartik's seeded backend
   and ElevenLabs setup. The phone's typed phrase input uses `/listen_text`
   if the mic is denied or the room is noisy.

| Input | Behavior |
| --- | --- |
| Single press, no card | Start or pause listening |
| Single press, card showing | Queue question; show confirmation for 2 seconds |
| Swipe down | Mute term and advance |
| Swipe up | Next waiting card, or replay the last card when empty |
| Long press / release | End meeting and prepare drafts |
| Double press | Native system exit confirmation, `shutDownPageContainer(1)` |
| Phone End meeting | Reliable alternative if the OS claims long press |

Cards expire after 8 seconds. Extra cards wait their turn. All display
updates use matching container IDs and names with `textContainerUpgrade`.
The glasses text currently uses ASCII labels instead of unverified symbols.

Live audio is raw PCM, signed 16-bit little endian, 16 kHz mono, uploaded in
128,000-byte (4-second) chunks. A final partial chunk is flushed on pause/end.
Requests abort after 6 seconds; at most one audio upload and one waiting
chunk are retained. Under a slow connection older waiting speech is dropped
to keep latency bounded. Backgrounding pauses capture; resume explicitly
when returning. No full transcript is stored by the client.

Keep the phone page open through draft approval. Session/queue authority is
on the backend, but the frozen API has no session-recovery endpoint, so a
full page reload loses this client's current session and unsent draft view.
Before judging, check a five-minute phone lock, denied mic, long press,
exit-dialog cancellation, actual glyph legibility and the live audio loop.

## Build and Beta package

```sh
npm test
npm run build
npm run pack:demo
```

The demo package is `glasses/footnote-demo.ehpk`. It contains the offline
mock flow and does not deliver email. For a **live** package, fill the
glasses env file, set `MOCK_MODE=false`, and run:

```sh
npm run pack
```

Upload **`glasses/footnote.ehpk`** to your Footnote app in the
[Even Hub developer portal](https://hub.evenrealities.com). Under **Builds**,
create/upload a build, distribute it to a **Beta** group containing your
phone account, then install from **Me → Beta tester** in the phone app.
Retest the complete loop after installation. Upload the demo package only
when deliberately testing an offline Beta. Portal upload and installation
require your account and are not performed by the local build command.

`glasses/app.json` is the base manifest. The build emits `glasses/dist/app.json`
with a network permission containing **only BACKEND_URL's origin** in live
mode; offline demo builds require no network permission. The pack script
uses this generated manifest, the installed SDK version (`0.0.16`) and its
minimum app version. It refuses to label a mock build as the live package.
No `.env` files or provider keys are packaged.

For simulator automation:

```sh
npm run simulate -- --automation-port 9898
curl http://127.0.0.1:9898/api/ping
curl -X POST -H 'Content-Type: application/json' \
  -d '{"action":"click"}' http://127.0.0.1:9898/api/input
```

The simulator keeps the native startup page across Vite reloads. If startup
returns code 1 after edits, close and relaunch the simulator. Glasses PNG
captures contain transparency; composite over black for visual inspection.

The digest builds into `web/dist`, which can be hosted by any static host.
Set its live env before building. Point the hackathon domain at that host
after deployment. No hosting account or domain changes are made here.

## Verification and remaining event work

`npm test` uses Node's built-in test runner for PCM integrity, API validation,
timeouts, config/manifest generation, gestures, fade-out, timers and meeting
failure handling. `npm run build` type-checks and builds both apps. The mock
flow proves client behavior; real email and transcription depend on Kartik.

The implementation follows the [official ASR starter](https://github.com/even-realities/evenhub-templates/tree/main/asr)
and [Even development instructions](https://github.com/even-realities/everything-evenhub).
Paper Desktop design work, physical G2 checks, Beta installation, demo video,
and Devpost submission still require the event devices/accounts. No Paper
usage or sponsor submission is claimed by this code setup.
