import io
import json
import re
from urllib.error import HTTPError, URLError
from unittest.mock import patch

import pytest
from followups import Followups

DRAFT = {"draft_id": "d_saved001", "to_name": "Dana Okafor", "to_email": "dana@halcyon.example",
         "subject": "Question about SLO", "body": "Hi Dana, could we review SLO?", "terms": ["SLO"]}
PAYLOAD = {"session_id": "s_latest001", "drafts": [DRAFT]}


def response(value):
    return io.BytesIO(json.dumps(value).encode())


@pytest.fixture
def tools():
    return Followups("https://backend.example", "private-test-token")


def preview(tools, sender="sender-one", conversation="chat-one"):
    with patch("urllib.request.urlopen", return_value=response(PAYLOAD)) as get:
        text = tools.reply("@footnote-jargon-decoder Show the questions I saved in my last meeting.", sender, conversation)
    assert isinstance(text, str) and "Subject: Question about SLO" in text
    assert "Hi Dana, could we review SLO?" in text
    assert "demo inbox" in text and "Nothing sent" in text
    assert get.call_count == 1
    req = get.call_args.args[0]
    assert req.get_method() == "GET" and req.full_url.endswith("/agent/drafts/pending")
    assert req.get_header("Authorization") == "Bearer private-test-token"
    return re.search(r"Approve ([A-Za-z0-9_-]+)", text).group(1)


def test_preview_is_read_only_and_approval_sends_one_draft_once(tools):
    code = preview(tools)
    with patch("urllib.request.urlopen", return_value=response({"sent": True})) as post:
        text = tools.reply("Approve " + code, "sender-one", "chat-one")
        assert "Sent" in text and "Dana" in text
        assert post.call_count == 1
        assert post.call_args.args[0].full_url == "https://backend.example/drafts/d_saved001/send"
        assert post.call_args.args[0].get_method() == "POST"
        assert "Already sent" in tools.reply("Approve " + code, "sender-one", "chat-one")
        assert post.call_count == 1


@pytest.mark.parametrize("sender,conversation,command", [
    ("other", "chat-one", "approve"), ("sender-one", "other-chat", "approve"),
    ("sender-one", "chat-one", "yes"), ("sender-one", "chat-one", "Approve invalid"),
    ("sender-one", "chat-one", "Approve {code} and everything else"),
])
def test_only_exact_approval_in_the_previewing_conversation_can_send(tools, sender, conversation, command):
    code = preview(tools)
    command = "Approve " + code if command == "approve" else command.format(code=code)
    with patch("urllib.request.urlopen") as post:
        text = tools.reply(command, sender, conversation)
        assert isinstance(text, str) and "Sent to" not in text
        post.assert_not_called()


def test_cancel_and_expiry_clear_only_that_conversations_permission(tools):
    with patch("followups.time.monotonic", return_value=1):
        code = preview(tools)
        other_code = preview(tools, "other", "other-chat")
        assert "Cancelled" in tools.reply("Cancel", "sender-one", "chat-one")
        with patch("urllib.request.urlopen", return_value=response({"sent": True})) as post:
            assert "preview" in tools.reply("Approve " + code, "sender-one", "chat-one").lower()
            post.assert_not_called()
            assert "Sent" in tools.reply("Approve " + other_code, "other", "other-chat")
        expired_code = preview(tools)
    with patch("followups.time.monotonic", return_value=602), patch("urllib.request.urlopen") as post:
        assert "preview" in tools.reply("Approve " + expired_code, "sender-one", "chat-one").lower()
        post.assert_not_called()


def test_refresh_invalidates_old_codes(tools):
    old = preview(tools)
    current = preview(tools)
    assert old != current
    with patch("urllib.request.urlopen", return_value=response({"sent": True})) as post:
        assert "preview" in tools.reply("Approve " + old, "sender-one", "chat-one").lower()
        post.assert_not_called()
        assert "Sent" in tools.reply("Approve " + current, "sender-one", "chat-one")


@pytest.mark.parametrize("failure", [URLError("offline"), TimeoutError(),
    HTTPError("https://backend.example", 502, "provider failure", {}, None)])
def test_failed_or_uncertain_send_keeps_same_code_for_explicit_retry(tools, failure):
    code = preview(tools)
    with patch("urllib.request.urlopen", side_effect=failure):
        text = tools.reply("Approve " + code, "sender-one", "chat-one")
        assert "confirm" in text.lower() and "retry" in text.lower()
    with patch("urllib.request.urlopen", return_value=response({"sent": True})) as post:
        assert "Sent" in tools.reply("Approve " + code, "sender-one", "chat-one")
        assert post.call_args.args[0].full_url.endswith("/drafts/d_saved001/send")


def test_phone_side_discard_is_not_reported_as_sent(tools):
    code = preview(tools)
    with patch("urllib.request.urlopen", side_effect=HTTPError("https://backend.example", 409, "discarded", {}, None)):
        text = tools.reply("Approve " + code, "sender-one", "chat-one")
        assert "no longer available" in text.lower()
    with patch("urllib.request.urlopen") as post:
        assert "preview" in tools.reply("Approve " + code, "sender-one", "chat-one").lower()
        post.assert_not_called()


@pytest.mark.parametrize("payload", [[], {"drafts": None}, {"session_id": "s_1", "drafts": [{}]},
    {"session_id": "s_1", "drafts": [{**DRAFT, "draft_id": "../bad"}]},
    {"session_id": "s_1", "drafts": [{**DRAFT, "body": None}]},
    {"session_id": None, "drafts": [DRAFT]}])
def test_bad_backend_payload_never_creates_an_approval(tools, payload):
    with patch("urllib.request.urlopen", return_value=response(payload)):
        text = tools.reply("Show my pending drafts", "sender-one", "chat-one")
        assert "could not" in text.lower()
        assert "Approve " not in text


def test_empty_pending_list_and_missing_config_are_clear(tools):
    with patch("urllib.request.urlopen", return_value=response({"session_id": "s_1", "drafts": []})):
        assert "no pending" in tools.reply("Send my questions", "sender-one", "chat-one").lower()
    with patch("urllib.request.urlopen") as get:
        assert "not configured" in Followups("https://backend.example", "").reply("Send my questions", "sender-one", "chat-one")
        get.assert_not_called()
    assert tools.reply("What does Bluebird mean?", "sender-one", "chat-one") is None


def test_bounded_reviews_and_restart_fail_closed(tools):
    with patch("followups.MAX_CONVERSATIONS", 2):
        old = preview(tools, "old", "old-chat")
        retained = preview(tools, "retained", "retained-chat")
        preview(tools, "new", "new-chat")
    with patch("urllib.request.urlopen") as post:
        assert "preview" in tools.reply("Approve " + old, "old", "old-chat").lower()
        fresh = Followups("https://backend.example", "private-test-token")
        assert "preview" in fresh.reply("Approve " + retained, "retained", "retained-chat").lower()
        assert "conversation" in tools.reply("Send my questions", "sender-one", "").lower()
        post.assert_not_called()


def test_unconfirmed_success_payload_never_claims_delivery(tools):
    code = preview(tools)
    with patch("urllib.request.urlopen", return_value=response({"sent": "true"})):
        assert "could not confirm" in tools.reply("Approve " + code, "sender-one", "chat-one").lower()
    with patch("urllib.request.urlopen", return_value=response({"sent": True})):
        assert "Sent" in tools.reply("Approve " + code, "sender-one", "chat-one")
