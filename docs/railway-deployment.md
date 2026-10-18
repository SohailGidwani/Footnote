# Railway deployment

Use three services in the same Railway project: `backend`, `agent`, and `web`. Build them
from the repository root. Keep all real values in Railway variables or ignored
local env files; do not put keys, the agent seed, inbox address or deployment URL
in this guide.

With the official Railway CLI installed, run `railway login` and `railway link`
to select the Footnote project and production environment before these commands.

## Backend

1. Use the existing `backend/Dockerfile`. Set
   `RAILWAY_DOCKERFILE_PATH=backend/Dockerfile` and `PORT=8000`.
2. Attach a volume at `/var/data`; set `DB_PATH=/var/data/footnote.db`.
   The image's `/tmp` default is temporary storage.
3. Add `ELEVENLABS_API_KEY`, `STEPFUN_API_KEY`, `RESEND_API_KEY`, and `DEMO_INBOX`
   as service variables. Set `NEW_HIRE_NAME=Sohail` and `ENABLE_DEBUG_RESET=0`.
   Preserve any intentional local STT/model overrides when copying configuration.
4. Use one replica and one Uvicorn worker, disable sleeping, and set the
   health-check path to `/health`. Active sessions and background tasks live
   in memory, so start a new meeting after a restart or deployment.
   Set deployment overlap to zero for this single-volume service.
5. Deploy from the repo root with `railway up --service backend`.
   Generate a Railway HTTPS domain targeting port 8000.

For existing meeting history, make a consistent snapshot using SQLite's backup
API. Railway volume file transfer requires a running service and a registered
SSH key. Start the service with `DB_PATH=/var/data/bootstrap.db`, upload the
snapshot as the separate volume file `/footnote.db`, verify it, then change
`DB_PATH` to `/var/data/footnote.db` and redeploy. Never overwrite an open SQLite
database or bake a database into the image. Keep the local snapshot private.

## Agent

1. Use `agent/Dockerfile` from the repo root. Set
   `RAILWAY_DOCKERFILE_PATH=agent/Dockerfile` and `PORT=8001`.
2. Set `AGENT_SEED` to the existing private seed from the ignored `agent/.env`.
   Set `BACKEND_URL` to the deployed backend's HTTPS origin and add
   `STEPFUN_API_KEY` for personalized prep. The agent does not need the profile
   management API token to run.
3. Use one replica, disable sleeping, and set the health-check path to
   `/agent_info`. A public agent domain is unnecessary in mailbox mode.
   Set deployment overlap to zero so two copies do not consume the same mailbox.
4. Stop the local agent before starting the cloud copy. Run only one process
   for this identity so competing mailbox consumers do not split messages.
5. Deploy with `railway up --service agent`. Check that startup reports the
   existing address, publishes ACP and registers with Agentverse.

## Web digest dashboard

1. Use `web/Dockerfile` from the repo root. Set
   `RAILWAY_DOCKERFILE_PATH=web/Dockerfile`, `PORT=80`, `MOCK_MODE=false`, and
   `BACKEND_URL` to the backend's HTTPS origin. This service needs no provider keys.
2. Use one replica and the health-check path `/`. Deploy with
   `railway up --service web`, then generate an HTTPS domain targeting port 80.
3. The backend origin is baked into the static bundle. If it changes, rebuild
   with `railway up`; a restart alone cannot update the JavaScript.
4. Verify the page, JavaScript and CSS load over HTTPS, then check the digest
   in a browser. API/asset checks alone do not prove browser rendering.

## Verify and connect clients

1. Check `GET /health` and an `OPTIONS /listen` preflight on the HTTPS backend.
   Confirm `POST /debug/reset` returns 404 on the public service.
2. Confirm the imported digest and Ridgeline definition survive redeployment.
   Run a typed session through cards, queue, mute, end and draft; sending email
   is a separate explicit test.
3. Test Bluebird lookup, Ridgeline lookup and personalized prep in ASI:One web
   after the cloud agent starts. Local generation alone does not prove delivery.
4. Put the deployed origin in ignored `glasses/.env.local` and `web/.env.local`
   with `MOCK_MODE=false`, then restart Vite for development checks.
5. Build the final live G2 package only after the backend origin is stable:
   `npm test`, then `npm run pack`. The origin is baked into
   `glasses/footnote.ehpk`; changing it requires rebuilding and uploading again.
   Follow Even Hub's Beta upload/install flow and test on the actual G2.
