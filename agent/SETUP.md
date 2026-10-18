# Footnote agent local setup

## macOS on this checkout

Use the backend's existing Python 3.11 to create an isolated agent environment.
From the repository root:

```sh
backend/.venv/bin/python -m venv agent/.venv
uv pip install --python agent/.venv/bin/python -r agent/requirements.txt pytest
cd agent
.venv/bin/python -m pytest -q
.venv/bin/python agent.py
```

Keep the existing ignored `agent/.env` unchanged: it holds this agent's registered
identity. Running the explicit `.venv/bin/python` avoids accidentally using Conda.
Never run with the example seed. On a fresh setup, generate a private value with
`openssl rand -hex 32`, put it in `AGENT_SEED`, and keep it stable after registration.
The previous Conda environment mixed `aiohttp 3.14.3` with `brotlicffi 1.0.9.2`,
causing `Can not decode content-encoding: br` during mailbox polling and reply
resolution. The clean environment avoids that incompatible optional decoder.

## Windows / fresh environment

Use Python 3.11 or later. From `agent/`:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
Copy-Item .env.example .env
# Replace AGENT_SEED in .env with a long private value; keep it unchanged after registration.
.venv/Scripts/python.exe agent.py
```

On this checkout, the ignored `.env` with a generated private seed already exists; do not overwrite it. On a fresh clone, copy the example and set a new seed. Start the backend separately on `http://localhost:8000` for digest questions. Glossary questions work from `data/company_pack.json` even when the backend is stopped. `BACKEND_URL` can be changed in the ignored `.env` when the backend is deployed. Keep the agent process running to answer chats.

If a requested term is absent from the pack, the agent checks the read-only
`GET /digest` for a matching learned definition from the last 24 hours. Model
inferences are labeled as inferred, with a suggested contact rather than a
confirmed owner. Unknown terms stay unknown; a lookup does not call `/listen_text`
or create a sighting. Learn the full name and its context in a meeting first.

## Personalized meeting prep

Add `STEPFUN_API_KEY` to the ignored `agent/.env` to enable StepFun
`step-5-preview` for prep requests, then restart the agent. Keep the seed unchanged.
The agent calls StepFun directly for prep only; it uses the same provider as the
backend but does not import the backend or change its API. No extra dependency
is required. Never put the key in the public profile or a client env file.

Try `Prepare me for a telemetry review about Ridgeline and FCS`, then
`Prep me for an incident review about SLO and runbook`. The agent reads the pack
and `GET /digest` from `BACKEND_URL`, asks StepFun to choose up to five saved term
IDs and three questions, validates the response, and renders meanings and contacts
from the original records. Inferred meeting definitions stay labeled inferred;
their contacts remain suggestions. Glossary definitions take precedence.
Agenda keywords shortlist up to 12 candidates before model selection; a request
without keyword matches gives the model the full pack for semantic matching.

If history is unavailable, prep uses the glossary and says so. If the key is
missing, the model times out (45 seconds), or its plan is invalid, it returns a
brief labeled **Keyword fallback** with three template questions. The platform
sync retains its original five-term fallback. No matching terms means the agent
asks for more context. There is no calendar access or automatic sending.

Console lines `prep model=step-5-preview llm_ms=... terms=...` confirm live model
selection; `prep fallback=keyword` identifies fallback. These timings cover the
model call and validation, not ASI:One transport or total response time.
Live local checks took about 18 and 33 seconds for two different agendas. This
is separate from the glasses listen path and its unchanged six-second timeout.

## Connect to Agentverse

The current local agent is **Footnote Jargon Decoder**, handle
`@footnote-jargon-decoder`: [open its ASI:One page](https://asi1.ai/ai/agent1qtm5jg9yr7e35ysxxahsvwc84g2yx95dkljesugg9xvdwmy8lp655tm2u2r).
Its seed is stored only in the ignored local `.env`. The previous placeholder-seed
identity is retired; use the new page rather than an old chat.

While the agent is running, open the Agent Inspector URL printed in its console in a normal browser on this computer, so the page can reach `127.0.0.1:8001`. Sign in to Agentverse, select **Connect > Mailbox**, and finish the connection. In the Agent Profile, use the name **Footnote Jargon Decoder**, add a handle, and paste the description and examples from `README.md` into the Overview editor. Confirm the chat protocol is listed. Then ask the agent in ASI:One: "What does Bluebird mean at Halcyon?" Mailbox mode does not require a public backend URL for registration, but the local agent must stay running. Keep the seed private and stable so its address does not change.

Open the full `https://agentverse.ai/inspect/...` link, not the server root
`http://0.0.0.0:8001/`. The root intentionally returns `{"error":"not found"}`;
`http://127.0.0.1:8001/agent_info` is the local identity/status endpoint.

If `README.md` changes after the initial mailbox connection, check the public profile. The initial README may remain published until you save an update through the Agentverse Overview editor.
