"""Private read tool must not change the existing phone/email workflow."""
import pytest
from .conftest import say

AUTH = {"Authorization": "Bearer test-agent-secret"}
PATH = "/agent/drafts/pending"


def finish(client, phrase):
    sid = client.post("/session/start").json()["session_id"]
    cards = say(client, sid, phrase)["cards"]
    for card in cards:
        assert client.post(f"/cards/{card['card_id']}/queue", json={"session_id": sid}).status_code == 200
    return sid, client.post(f"/session/{sid}/end").json()["drafts"]


def test_private_tool_disabled_without_configuration(client, monkeypatch):
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    assert client.get(PATH, headers=AUTH).status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}])
def test_private_tool_rejects_bad_authorization(client, monkeypatch, headers):
    monkeypatch.setenv("AGENT_API_TOKEN", "test-agent-secret")
    response = client.get(PATH, headers=headers)
    assert response.status_code == 401
    assert "drafts" not in response.json()


def test_private_tool_returns_only_latest_ended_meeting_and_does_not_write(client, monkeypatch):
    monkeypatch.setenv("AGENT_API_TOKEN", "test-agent-secret")
    assert client.get(PATH, headers=AUTH).json() == {"session_id": None, "drafts": []}
    old, _ = finish(client, "Bluebird")
    latest, drafts = finish(client, "SLO and Kestrel")
    active = client.post("/session/start").json()["session_id"]
    card = say(client, active, "Tern")["cards"][0]
    client.post(f"/cards/{card['card_id']}/queue", json={"session_id": active})
    store = client.app.state.footnote.store
    before = list(store.conn.iterdump())
    assert client.get(PATH, headers=AUTH).json() == {"session_id": latest, "drafts": drafts}
    assert list(store.conn.iterdump()) == before
    assert latest != old


def test_private_tool_omits_sent_and_discarded_drafts(client, monkeypatch, fake_mail):
    monkeypatch.setenv("AGENT_API_TOKEN", "test-agent-secret")
    sid, drafts = finish(client, "SLO and Kestrel")
    assert client.post(f"/drafts/{drafts[0]['draft_id']}/send").status_code == 200
    assert client.get(PATH, headers=AUTH).json() == {"session_id": sid, "drafts": [drafts[1]]}
    assert client.post(f"/drafts/{drafts[1]['draft_id']}/discard").status_code == 200
    assert client.get(PATH, headers=AUTH).json() == {"session_id": sid, "drafts": []}
    assert len(fake_mail) == 1


def test_empty_latest_meeting_does_not_resurface_old_pending_drafts(client, monkeypatch):
    monkeypatch.setenv("AGENT_API_TOKEN", "test-agent-secret")
    finish(client, "Bluebird")
    latest, _ = finish(client, "nothing unfamiliar here")
    assert client.get(PATH, headers=AUTH).json() == {"session_id": latest, "drafts": []}
