import asyncio
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import llm, mailer, stt
from app.main import slow_path

from .conftest import say


def test_health_and_cors_preflight(client):
    assert client.get("/health").json() == {"ok": True}
    r = client.options("/listen", headers={"Origin": "https://phone.example",
                                           "Access-Control-Request-Method": "POST",
                                           "Access-Control-Request-Headers": "content-type"})
    assert r.status_code == 204
    assert r.headers["access-control-allow-origin"] == "*"
    assert "POST" in r.headers["access-control-allow-methods"]
    assert "content-type" in r.headers["access-control-allow-headers"]
    # real responses (including errors) carry the headers too
    err = client.post("/listen_text", json={"session_id": "nope", "text": "x"}, headers={"Origin": "https://x.example"})
    assert err.status_code == 404 and err.headers["access-control-allow-origin"] == "*"


def test_card_matches_contract_shape(client, session):
    out = say(client, session, "Bluebird is blocked")
    assert out["transcript"] == "Bluebird is blocked"
    (card,) = out["cards"]
    assert set(card) == {"card_id", "term_id", "term", "line1", "owner_name", "owner_team", "source", "confidence"}
    assert card["term"] == "BLUEBIRD" and card["line1"] == "v3 navigation stack rewrite"
    assert (card["owner_name"], card["owner_team"]) == ("Priya R.", "Autonomy")
    assert card["source"] == "glossary" and card["confidence"] == 1.0
    assert len(card["term"]) <= 24 and len(card["line1"]) <= 44 and len(card["owner_name"] + card["owner_team"]) <= 40


def test_at_most_two_cards_and_overflow_arrives_next(client, session):
    first = say(client, session, "Bluebird, FCS, Kestrel and the golden path")["cards"]
    assert [c["term"] for c in first] == ["BLUEBIRD", "FCS"]
    second = say(client, session, "anyway")["cards"]
    assert [c["term"] for c in second] == ["KESTREL", "GOLDEN PATH"]
    assert say(client, session, "anyway")["cards"] == []


def test_waiting_slow_path_card_takes_next_response_slot(client, session):
    state = client.app.state.footnote
    tid = state.store.add_llm_term("HAL-9", "Legacy robot health monitor", "p_marcus", 0.8)
    state.session(session).pending.append(tid)
    first = say(client, session, "Bluebird and FCS")["cards"]
    assert [c["term"] for c in first] == ["HAL-9", "BLUEBIRD"]
    assert [c["term"] for c in say(client, session, "ok")["cards"]] == ["FCS"]


def test_each_term_shows_once_per_meeting(client, session):
    assert len(say(client, session, "Bluebird")["cards"]) == 1
    assert say(client, session, "Bluebird again")["cards"] == []


def test_session_reconstruction_preserves_shown_cards(client, session):
    assert len(say(client, session, "Bluebird")["cards"]) == 1
    state = client.app.state.footnote
    state.sessions.pop(session)  # simulate the in-memory state lost on restart
    assert say(client, session, "Bluebird again")["cards"] == []
    assert state.store.seen_state("t_bluebird")[0] == 1


def test_fade_out_after_three_sightings(client):
    for _ in range(3):
        sid = client.post("/session/start", json={}).json()["session_id"]
        assert len(say(client, sid, "Bluebird")["cards"]) == 1
    sid = client.post("/session/start", json={}).json()["session_id"]
    assert say(client, sid, "Bluebird")["cards"] == []


def test_mute_hides_term_for_good(client, session):
    card = say(client, session, "FCS")["cards"][0]
    assert client.post(f"/terms/{card['term_id']}/mute", json={}).json() == {"muted": True}
    sid = client.post("/session/start", json={}).json()["session_id"]
    assert say(client, sid, "FCS again")["cards"] == []
    assert client.post("/terms/nope/mute", json={}).status_code == 404


def test_queue_end_send_flow(client, session, fake_mail, monkeypatch):
    async def no_stepfun(owner, items, new_hire, system):
        raise RuntimeError("down")  # exercise the template fallback

    monkeypatch.setattr(llm, "draft_message", no_stepfun)
    cards = say(client, session, "Bluebird and geofence and FCS")["cards"]
    assert [c["term"] for c in cards] == ["BLUEBIRD", "GEOFENCE"]
    for c in cards:
        r = client.post(f"/cards/{c['card_id']}/queue", json={"session_id": session})
        assert r.json() == {"queued": True, "owner_name": "Priya R."}
    client.post(f"/cards/{cards[0]['card_id']}/queue", json={"session_id": session})  # repeat press: no duplicate

    preview = client.app.state.footnote.store.drafts_for_session(session)
    assert len(preview) == 1 and preview[0]["terms"] == ["Bluebird", "geofence"]
    assert client.post(f"/drafts/{preview[0]['draft_id']}/send").status_code == 409

    drafts = client.post(f"/session/{session}/end").json()["drafts"]
    assert len(drafts) == 1  # both terms belong to Priya, so one batched message
    d = drafts[0]
    assert set(d) == {"draft_id", "to_name", "to_email", "subject", "body", "terms"}
    assert d["to_name"] == "Priya Raman" and d["to_email"] == "priya@halcyon.example"
    assert d["subject"] == "To Priya R.: quick question about Bluebird and geofence"
    assert d["terms"] == ["Bluebird", "geofence"] and "Hi Priya" in d["body"]
    assert client.post(f"/session/{session}/end").json()["drafts"] == drafts  # idempotent

    assert fake_mail == []  # nothing is sent before approval
    assert client.post(f"/drafts/{d['draft_id']}/send").json() == {"sent": True}
    assert client.post(f"/drafts/{d['draft_id']}/send").json() == {"sent": True}
    assert len(fake_mail) == 1 and fake_mail[0]["subject"] == d["subject"]
    assert fake_mail[0]["to"] == "priya@halcyon.example"
    assert fake_mail[0]["draft_id"] == d["draft_id"]
    assert client.post("/drafts/nope/send").status_code == 404


def test_queue_rejects_wrong_session_and_ended_session(client, session):
    card = say(client, session, "Bluebird")["cards"][0]
    other = client.post("/session/start", json={}).json()["session_id"]
    assert client.post(f"/cards/{card['card_id']}/queue", json={"session_id": other}).status_code == 404
    client.post(f"/session/{session}/end")
    assert client.post(f"/cards/{card['card_id']}/queue", json={"session_id": session}).status_code == 409
    assert client.post("/listen_text", json={"session_id": session, "text": "FCS"}).status_code == 409


def test_end_returns_promptly_while_stepfun_draft_is_slow(client, session, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "fake")

    async def slow_draft(*args):
        await asyncio.sleep(10)
        return "late draft"

    monkeypatch.setattr(llm, "draft_message", slow_draft)
    card = say(client, session, "Bluebird")["cards"][0]
    client.post(f"/cards/{card['card_id']}/queue", json={"session_id": session})
    start = time.perf_counter()
    response = client.post(f"/session/{session}/end", json={})
    assert response.status_code == 200
    assert time.perf_counter() - start < 1
    (draft,) = response.json()["drafts"]
    assert "Bluebird" in draft["body"] and "late draft" not in draft["body"]
    time.sleep(0.05)
    assert client.app.state.footnote.store.drafts_for_session(session) == [draft]


def test_background_draft_refresh_uses_latest_queue_and_freezes_at_end(client, session, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "fake")

    async def draft_message(owner, items, new_hire, system):
        await asyncio.sleep(0.05)
        return "Prepared: " + ", ".join(item["term"] for item in items)

    monkeypatch.setattr(llm, "draft_message", draft_message)
    cards = say(client, session, "Bluebird and geofence")["cards"]
    for card in cards:
        client.post(f"/cards/{card['card_id']}/queue", json={"session_id": session})
    time.sleep(0.2)
    preview = client.app.state.footnote.store.drafts_for_session(session)[0]
    assert preview["body"] == "Prepared: Bluebird, geofence"
    assert client.post(f"/session/{session}/end").json()["drafts"] == [preview]


def test_stale_background_draft_cannot_replace_newer_queue(client, session, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "fake")

    async def slow_draft(owner, items, new_hire, system):
        await asyncio.sleep(0.2)
        return "Outdated: " + ", ".join(item["term"] for item in items)

    monkeypatch.setattr(llm, "draft_message", slow_draft)
    cards = say(client, session, "Bluebird and geofence")["cards"]
    client.post(f"/cards/{cards[0]['card_id']}/queue", json={"session_id": session})
    client.post(f"/cards/{cards[1]['card_id']}/queue", json={"session_id": session})
    time.sleep(0.3)
    preview = client.app.state.footnote.store.drafts_for_session(session)[0]
    assert preview["body"] == "Outdated: Bluebird, geofence"


def test_hal9_contextual_fallback_is_hedged_and_owned_by_marcus(client, session, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "fake")

    async def malformed(*args):
        return [{"term": "HAL-9", "is_company_term": False, "meaning": None,
                 "owner_id": "", "confidence": "low"}]

    monkeypatch.setattr(llm, "explain", malformed)
    state = client.app.state.footnote
    asyncio.run(slow_path(state, state.session(session), "Did Marcus update the HAL-9 runbook?"))
    cards = say(client, session, "ok")["cards"]
    assert [(c["term"], c["line1"], c["owner_name"], c["confidence"]) for c in cards] == [
        ("HAL-9", "Internal code; details unconfirmed", "Marcus L.", 0.6)]


def test_hal9_contextual_fallback_survives_stepfun_timeout(client, session, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "fake")
    monkeypatch.setattr("app.main.SLOW_PATH_CAP_S", 0.01)

    async def slow(*args):
        await asyncio.sleep(1)

    monkeypatch.setattr(llm, "explain", slow)
    state = client.app.state.footnote
    asyncio.run(slow_path(state, state.session(session), "Did Marcus update the HAL-9 runbook?"))
    assert [card["term"] for card in say(client, session, "ok")["cards"]] == ["HAL-9"]


def test_hal9_salvages_malformed_fields_with_valid_model_owner(client, session, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "fake")

    async def malformed(*args):
        return [{"term": "HAL-9", "is_company_term": True, "meaning": None,
                 "owner_id": "p_marcus", "confidence": "low"}]

    monkeypatch.setattr(llm, "explain", malformed)
    state = client.app.state.footnote
    asyncio.run(slow_path(state, state.session(session), "HAL-9 is down"))
    cards = say(client, session, "ok")["cards"]
    assert [(c["term"], c["owner_name"], c["confidence"]) for c in cards] == [
        ("HAL-9", "Marcus L.", 0.6)]


def test_stepfun_prompt_allows_uncatalogued_contextual_codes(monkeypatch):
    seen = []

    async def fake_chat(messages, effort, schema):
        seen.extend(messages)
        return '{"terms":[]}'

    monkeypatch.setattr(llm, "_chat", fake_chat)
    asyncio.run(llm.explain("system", "Did Marcus update HAL-9?", ["HAL-9"]))
    assert "need not appear in the company pack" in seen[1]["content"]
    assert "never a word" in seen[1]["content"]


def test_failed_send_keeps_draft_retryable(client, session, monkeypatch):
    async def boom(*a):
        raise mailer.MailError("down")

    monkeypatch.setattr(mailer, "send", boom)
    card = say(client, session, "Bluebird")["cards"][0]
    client.post(f"/cards/{card['card_id']}/queue", json={"session_id": session})
    (d,) = client.post(f"/session/{session}/end").json()["drafts"]
    assert client.post(f"/drafts/{d['draft_id']}/send").status_code == 502
    assert client.get("/digest").json()["sent"] == []


def test_send_deadline_keeps_draft_retryable(client, session, monkeypatch):
    async def slow_send(*args):
        await asyncio.sleep(1)

    monkeypatch.setattr(mailer, "send", slow_send)
    monkeypatch.setattr("app.main.SEND_CAP_S", 0.01)
    card = say(client, session, "Bluebird")["cards"][0]
    client.post(f"/cards/{card['card_id']}/queue", json={"session_id": session})
    draft = client.post(f"/session/{session}/end", json={}).json()["drafts"][0]
    assert client.post(f"/drafts/{draft['draft_id']}/send", json={}).status_code == 502
    assert client.app.state.footnote.store.draft(draft["draft_id"])["status"] == "draft"


def test_end_write_failure_rolls_back_and_retry_completes(client, session):
    cards = say(client, session, "Bluebird and FCS")["cards"]
    for card in cards:
        client.post(f"/cards/{card['card_id']}/queue", json={"session_id": session})
    store = client.app.state.footnote.store
    store.conn.execute("""CREATE TRIGGER fail_end BEFORE UPDATE ON sessions
        BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        client.post(f"/session/{session}/end", json={})
    assert store.session(session)["ended_at"] is None
    assert len(store.drafts_for_session(session)) == 2  # previews remain usable
    store.conn.execute("DROP TRIGGER fail_end")
    drafts = client.post(f"/session/{session}/end", json={}).json()["drafts"]
    assert {d["to_name"] for d in drafts} == {"Priya Raman", "Marcus Lindqvist"}


def test_end_repairs_partial_drafts_from_older_server(client, session):
    cards = say(client, session, "Bluebird and FCS")["cards"]
    for card in cards:
        client.post(f"/cards/{card['card_id']}/queue", json={"session_id": session})
    store = client.app.state.footnote.store
    store.conn.execute("DELETE FROM drafts WHERE session_id=? AND owner_id='p_marcus'", (session,))
    store.conn.execute("UPDATE sessions SET ended_at=1 WHERE id=?", (session,))
    store.conn.commit()
    drafts = client.post(f"/session/{session}/end", json={}).json()["drafts"]
    assert {d["to_name"] for d in drafts} == {"Priya Raman", "Marcus Lindqvist"}


def test_concurrent_end_creates_one_draft_per_owner(client, session, monkeypatch):
    async def slow_draft(owner, items, new_hire, system):
        await asyncio.sleep(0.05)
        return "Hi Priya, could you send a 2-line summary? Thanks, Alex"

    monkeypatch.setattr(llm, "draft_message", slow_draft)
    card = say(client, session, "Bluebird")["cards"][0]
    client.post(f"/cards/{card['card_id']}/queue", json={"session_id": session})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client.post, f"/session/{session}/end", json={}) for _ in range(2)]
        results = [future.result() for future in futures]
    assert all(result.status_code == 200 for result in results)
    assert len(results[0].json()["drafts"]) == len(results[1].json()["drafts"]) == 1
    assert results[0].json()["drafts"] == results[1].json()["drafts"]


def test_send_retry_reuses_provider_idempotency_key(client, session, fake_mail, monkeypatch):
    card = say(client, session, "Bluebird")["cards"][0]
    client.post(f"/cards/{card['card_id']}/queue", json={"session_id": session})
    draft = client.post(f"/session/{session}/end", json={}).json()["drafts"][0]
    store = client.app.state.footnote.store
    original = store.mark_sent

    def fail_once(draft_id):
        store.mark_sent = original
        raise RuntimeError("injected write failure after provider success")

    monkeypatch.setattr(store, "mark_sent", fail_once)
    with pytest.raises(RuntimeError):
        client.post(f"/drafts/{draft['draft_id']}/send", json={})
    assert store.draft(draft["draft_id"])["status"] == "draft"
    assert client.post(f"/drafts/{draft['draft_id']}/send", json={}).json() == {"sent": True}
    assert [call["draft_id"] for call in fake_mail] == [draft["draft_id"]] * 2


def test_mailer_uses_demo_inbox_and_provider_idempotency_header(monkeypatch):
    class FakeResponse:
        status_code = 200

    class FakeHttp:
        def __init__(self):
            self.calls = []

        async def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return FakeResponse()

    http = FakeHttp()
    monkeypatch.setattr(mailer, "_http", lambda: http)
    monkeypatch.setenv("RESEND_API_KEY", "fake-key")
    monkeypatch.setenv("DEMO_INBOX", "demo@example.com")
    asyncio.run(mailer.send("Subject", "Body", "priya@halcyon.example", "d_test"))
    _, kwargs = http.calls[0]
    assert kwargs["headers"]["Idempotency-Key"] == "d_test"
    assert kwargs["json"]["to"] == ["demo@example.com"]
    assert "priya@halcyon.example" in kwargs["json"]["text"]


def test_digest_reflects_the_meeting(client, session, fake_mail):
    card = say(client, session, "Bluebird and FCS")["cards"][0]
    client.post(f"/terms/{say(client, session, 'Kestrel')['cards'][0]['term_id']}/mute", json={})
    client.post(f"/cards/{card['card_id']}/queue", json={"session_id": session})
    (d,) = client.post(f"/session/{session}/end").json()["drafts"]
    client.post(f"/drafts/{d['draft_id']}/send")
    dig = client.get("/digest").json()
    assert {t["term"] for t in dig["terms_learned"]} == {"Bluebird", "FCS", "Kestrel"}
    assert dig["people_to_meet"][0]["name"] == "Priya Raman" and dig["people_to_meet"][0]["question_queued"]
    assert {p["name"] for p in dig["people_to_meet"]} == {"Priya Raman", "Marcus Lindqvist", "Tomas Reyes"}
    assert dig["sent"][0]["subject"] == d["subject"] and dig["sent"][0]["to_name"] == "Priya Raman"


def test_empty_digest(client):
    assert client.get("/digest").json() == {"terms_learned": [], "people_to_meet": [], "sent": []}


def test_listen_pcm_uses_stt_then_glossary(client, session, monkeypatch):
    calls = []

    async def fake_transcribe(pcm):
        calls.append(len(pcm))
        return "Bluebird is slipping"

    monkeypatch.setattr(stt, "transcribe", fake_transcribe)
    loud = (b"\x00\x20" * 32000)  # 4 s of non-silent PCM
    r = client.post(f"/listen?session_id={session}", content=loud, headers={"Content-Type": "application/octet-stream"})
    assert r.status_code == 200 and [c["term"] for c in r.json()["cards"]] == ["BLUEBIRD"]
    client.post(f"/listen?session_id={session}", content=loud)
    assert calls[1] == len(loud) + 400 * 32  # second chunk is prefixed with the previous tail


def test_listen_skips_stt_for_silence_and_reports_stt_failure(client, session, monkeypatch):
    async def fail(pcm):
        raise stt.SttError("x")

    monkeypatch.setattr(stt, "transcribe", fail)
    silent = bytes(64000)
    assert client.post(f"/listen?session_id={session}", content=silent).json() == {"transcript": "", "cards": []}
    assert client.post(f"/listen?session_id={session}", content=b"\x00\x20" * 32000).status_code == 502


def test_stt_deadline_reports_retryable_failure(client, session, monkeypatch):
    async def slow_transcribe(pcm):
        await asyncio.sleep(1)

    monkeypatch.setattr(stt, "transcribe", slow_transcribe)
    monkeypatch.setattr("app.main.STT_CAP_S", 0.01)
    assert client.post(f"/listen?session_id={session}", content=b"\x00\x20" * 32000).status_code == 502


def test_listen_validates_audio_size_and_sample_boundary(client, session):
    assert client.post(f"/listen?session_id={session}", content=b"\x00" * 3_201).status_code == 400
    assert client.post(f"/listen?session_id={session}", content=b"\x00" * 2_000_002).status_code == 413
    assert client.post("/listen_text", json={"session_id": session, "text": "x" * 4_097}).status_code == 422
    assert client.post("/listen_text", content=b" " * 32_769).status_code == 413


def test_slow_path_rejects_malformed_answer_and_can_retry(client, session, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "fake")
    state = client.app.state.footnote
    current = {"is_company_term": "false"}

    async def fake_explain(system, transcript, candidates):
        assert candidates == ["HAL-9"]
        return [{"term": "HAL-9", "is_company_term": current["is_company_term"],
                 "meaning": "Legacy robot health monitor", "owner_id": "p_marcus", "confidence": 0.8}]

    monkeypatch.setattr(llm, "explain", fake_explain)
    asyncio.run(slow_path(state, state.session(session), "HAL-9 is down"))
    assert state.session(session).pending == []
    current["is_company_term"] = True
    asyncio.run(slow_path(state, state.session(session), "HAL-9 is down"))
    cards = say(client, session, "ok")["cards"]
    assert [c["term"] for c in cards] == ["HAL-9"] and cards[0]["confidence"] == 0.7


def test_slow_path_cards_arrive_on_next_listen(client, session, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "fake")

    async def fake_explain(system, transcript, candidates):
        assert candidates == ["HAL-9"]  # Marcus is a known person, "Did" starts the sentence
        return [{"term": "HAL-9", "is_company_term": True, "meaning": "Legacy robot health monitor", "owner_id": "p_marcus", "confidence": 0.8}]

    monkeypatch.setattr(llm, "explain", fake_explain)
    first = say(client, session, "Did Marcus update the HAL-9 runbook?")
    assert [c["term"] for c in first["cards"]] == ["RUNBOOK"]  # the glossary card is not held up by StepFun
    time.sleep(0.2)  # let the background task finish
    second = say(client, session, "ok")
    llm_cards = [c for c in second["cards"] if c["source"] == "llm"]
    assert [c["term"] for c in llm_cards] == ["HAL-9"] and llm_cards[0]["owner_name"] == "Marcus L."
    assert llm_cards[0]["confidence"] == 0.7
    # cached: the next meeting matches it on the fast path, source stays "llm"
    sid = client.post("/session/start", json={}).json()["session_id"]
    assert [c["source"] for c in say(client, sid, "HAL-9 is down")["cards"]] == ["llm"]


def test_slow_path_failures_never_break_listen(client, session, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "fake")

    async def slow(system, transcript, candidates):
        await asyncio.sleep(10)

    monkeypatch.setattr("app.main.SLOW_PATH_CAP_S", 0.05)
    monkeypatch.setattr(llm, "explain", slow)
    assert say(client, session, "Is HAL-9 ready?")["cards"] == []
    assert say(client, session, "ok")["cards"] == []


def test_debug_reset_is_off_unless_enabled(client, monkeypatch):
    assert client.post("/debug/reset").status_code == 404
    monkeypatch.setenv("ENABLE_DEBUG_RESET", "1")
    sid = client.post("/session/start", json={}).json()["session_id"]
    say(client, sid, "Bluebird")
    assert client.post("/debug/reset").json() == {"reset": True}
    assert client.get("/digest").json()["terms_learned"] == []


def test_stepfun_quota_error_trips_a_short_circuit_breaker(monkeypatch):
    import httpx
    import openai
    import pytest

    calls = []

    class FakeCompletions:
        @staticmethod
        async def create(**kwargs):
            calls.append(kwargs)
            raise openai.APIStatusError("quota", response=httpx.Response(
                402, request=httpx.Request("POST", "https://api.stepfun.ai/v1/chat/completions")), body=None)

    class FakeClient:
        class chat:
            completions = FakeCompletions

    monkeypatch.setattr(llm, "_client", FakeClient)
    monkeypatch.setattr(llm, "_down_until", 0.0)
    for _ in range(3):
        with pytest.raises(Exception):
            asyncio.run(llm._chat([{"role": "user", "content": "hi"}], "low"))
    assert len(calls) == 1  # after the first 402 the rest fail fast without calling StepFun


def test_stepfun_retries_schema_without_reasoning_effort(monkeypatch):
    import httpx
    import openai
    from types import SimpleNamespace

    calls = []

    class FakeCompletions:
        @staticmethod
        async def create(**kwargs):
            calls.append(kwargs)
            if "reasoning_effort" in kwargs:
                raise openai.BadRequestError("unsupported effort", response=httpx.Response(
                    400, request=httpx.Request("POST", "https://api.stepfun.ai/v1/chat/completions")), body=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"terms":[]}'))])

    class FakeClient:
        class chat:
            completions = FakeCompletions

    monkeypatch.setattr(llm, "_client", FakeClient)
    monkeypatch.setattr(llm, "_down_until", 0.0)
    answer = asyncio.run(llm._chat([{"role": "user", "content": "hi"}], "low", llm.EXPLAIN_SCHEMA))
    assert answer == '{"terms":[]}'
    assert len(calls) == 2
    assert calls[1]["response_format"]["type"] == "json_schema"
    assert "reasoning_effort" not in calls[1]
