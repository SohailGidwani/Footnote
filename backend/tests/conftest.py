import json

import pytest
from fastapi.testclient import TestClient

from app import config, llm, mailer, stt
from app.main import create_app


@pytest.fixture(autouse=True)
def no_real_services(monkeypatch):
    """Tests never touch real keys or the network."""
    for name in ("ELEVENLABS_API_KEY", "STEPFUN_API_KEY", "RESEND_API_KEY", "DEMO_INBOX", "ENABLE_DEBUG_RESET"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def pack():
    return json.loads(config.pack_path().read_text(encoding="utf-8"))


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path / "t.db"))) as c:
        yield c


@pytest.fixture
def session(client):
    return client.post("/session/start", json={}).json()["session_id"]


def say(client, session, text):
    r = client.post("/listen_text", json={"session_id": session, "text": text})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def fake_mail(monkeypatch):
    sent = []

    async def fake_send(subject, body, display_to, draft_id):
        sent.append({"subject": subject, "body": body, "to": display_to, "draft_id": draft_id})

    monkeypatch.setattr(mailer, "send", fake_send)
    return sent
