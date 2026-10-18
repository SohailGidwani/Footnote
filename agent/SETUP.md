# Footnote agent local setup

Use Python 3.11 or later. From `agent/`:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
Copy-Item .env.example .env
# Replace AGENT_SEED in .env with a long private value; keep it unchanged after registration.
.venv/Scripts/python.exe agent.py
```

On this checkout, the ignored `.env` with a generated private seed already exists; do not overwrite it. On a fresh clone, copy the example and set a new seed. Start the backend separately on `http://localhost:8000` for digest questions. Glossary questions work from `data/company_pack.json` even when the backend is stopped. `BACKEND_URL` can be changed in the ignored `.env` when the backend is deployed. Keep the agent process running to answer chats.

## Connect to Agentverse

While the agent is running, open the Agent Inspector URL printed in its console in a normal browser on this computer, so the page can reach `127.0.0.1:8001`. Sign in to Agentverse, select **Connect > Mailbox**, and finish the connection. In the Agent Profile, use the name **Footnote: new-hire jargon decoder**, add a handle, and paste the description and examples from `README.md` into the Overview editor. Confirm the chat protocol is listed. Then ask the agent in ASI:One: "What does Bluebird mean at Halcyon?" Mailbox mode does not require a public backend URL for registration, but the local agent must stay running. Keep the seed private and stable so its address does not change.

If `README.md` changes after the initial mailbox connection, check the public profile. The initial README may remain published until you save an update through the Agentverse Overview editor.
