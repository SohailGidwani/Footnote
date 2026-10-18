![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

# Footnote: new-hire jargon decoder

Footnote helps a new Halcyon Robotics teammate understand company terms during onboarding. Ask it what a project or acronym means and it answers from the company glossary with the responsible person and team. It can also read the local Footnote meeting digest to recap terms learned and suggest people to meet. It does not record a new term sighting when you ask a question.

Keywords: onboarding, company glossary, jargon, acronyms, meeting recap, people to meet, Halcyon Robotics.

Example questions:

- What does Bluebird mean at Halcyon?
- What did I learn today?
- Who should I meet?

## Run locally

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

While the agent is running, open the Agent Inspector URL printed in its console in a normal browser on this computer, so the page can reach `127.0.0.1:8001`. Sign in to Agentverse, select **Connect > Mailbox**, and finish the connection. In the Agent Profile, use the name **Footnote: new-hire jargon decoder**, add a handle and the description above, and confirm the chat protocol is listed. Then ask the agent in ASI:One: "What does Bluebird mean at Halcyon?" Mailbox mode does not require a public backend URL for registration, but the local agent must stay running. Keep the seed private and stable so its address does not change.
