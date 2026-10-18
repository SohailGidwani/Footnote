"""Check the actual chat handler sends an acknowledgement and one text reply."""

import asyncio
import os
import unittest
from unittest.mock import patch

from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, TextContent

from agent import build_agent, handle_chat


class FakeContext:
    def __init__(self):
        self.sent = []

    async def send(self, recipient, message):
        self.sent.append((recipient, message))


class ChatProtocolTests(unittest.TestCase):
    @patch.dict(os.environ, {"AGENT_SEED": "replace-with-a-long-random-secret-and-keep-it-private"})
    @patch("agent.Agent")
    def test_rejects_public_example_seed(self, agent_class):
        with self.assertRaisesRegex(RuntimeError, "private AGENT_SEED"):
            build_agent()
        agent_class.assert_not_called()

    def test_bluebird_chat_message(self):
        ctx = FakeContext()
        incoming = ChatMessage(content=[TextContent(type="text", text="What does Bluebird mean at Halcyon?")])
        asyncio.run(handle_chat(ctx, "agent1sender", incoming))
        self.assertEqual(len(ctx.sent), 2)
        self.assertEqual(ctx.sent[0][0], "agent1sender")
        self.assertIsInstance(ctx.sent[0][1], ChatAcknowledgement)
        self.assertEqual(ctx.sent[0][1].acknowledged_msg_id, incoming.msg_id)
        self.assertEqual(ctx.sent[1][0], "agent1sender")
        self.assertIsInstance(ctx.sent[1][1], ChatMessage)
        self.assertIn("Priya Raman (Autonomy)", ctx.sent[1][1].content[0].text)

    @patch("footnote.fetch_digest", return_value={"terms_learned": []})
    def test_asi_mentions_preserve_unknown_term_questions(self, get_digest):
        for prefix in ("@agent1testrecipient ", "@agent1testrecipient \n"):
            with self.subTest(prefix=prefix):
                ctx = FakeContext()
                incoming = ChatMessage(content=[TextContent(
                    type="text", text=prefix + "What does Ridgeline mean at Halcyon?"
                )])
                asyncio.run(handle_chat(ctx, "agent1sender", incoming))
                self.assertIsInstance(ctx.sent[0][1], ChatAcknowledgement)
                self.assertIn("do not have Ridgeline", ctx.sent[1][1].content[0].text)

    @patch("footnote.fetch_digest", return_value={"terms_learned": [{
        "term": "Ridgeline", "meaning": "Telemetry migration to the new cluster",
        "owner_name": "Marcus Lindqvist", "owner_team": "Platform", "source": "llm",
    }]})
    def test_handle_mentions_can_lookup_learned_terms(self, get_digest):
        for prefix in ("@footnote-jargon-decoder ", "@footnote-jargon-decoder\n",
                       "@jargon_decoder ", "@halcyon.decoder "):
            with self.subTest(prefix=prefix):
                get_digest.reset_mock()
                ctx = FakeContext()
                incoming = ChatMessage(content=[TextContent(
                    type="text", text=prefix + "What does Ridgeline mean at Halcyon?"
                )])
                asyncio.run(handle_chat(ctx, "agent1sender", incoming))
                self.assertEqual(len(ctx.sent), 2)
                self.assertIsInstance(ctx.sent[0][1], ChatAcknowledgement)
                self.assertEqual(ctx.sent[0][1].acknowledged_msg_id, incoming.msg_id)
                reply = ctx.sent[1][1].content[0].text
                self.assertIn("Ridgeline: Telemetry migration to the new cluster", reply)
                self.assertIn("Inferred", reply)
                self.assertIn("Suggested contact: Marcus Lindqvist (Platform)", reply)
                get_digest.assert_called_once()

    def test_followup_tool_runs_after_ack_and_before_normal_answers(self):
        ctx = FakeContext()
        ctx.session = "conversation-one"
        class Tools:
            def reply(self, question, sender, conversation):
                assert isinstance(ctx.sent[0][1], ChatAcknowledgement)
                assert sender == "agent1sender" and conversation == "conversation-one"
                return "Subject: a saved question. Preview only."
        incoming = ChatMessage(content=[TextContent(type="text", text="Show my saved questions")])
        with patch("agent.followups", Tools(), create=True):
            asyncio.run(handle_chat(ctx, "agent1sender", incoming))
        self.assertIn("Subject: a saved question", ctx.sent[1][1].content[0].text)

    @patch.dict(os.environ, {"STEPFUN_API_KEY": ""})
    @patch("footnote.fetch_digest", return_value={"terms_learned": [], "people_to_meet": [], "sent": []})
    def test_asi_prep_message_returns_a_brief_after_acknowledgement(self, _get_digest):
        ctx = FakeContext()
        incoming = ChatMessage(content=[TextContent(
            type="text", text="@agent1testrecipient Prep me for an incident review about SLO and runbook"
        )])
        asyncio.run(handle_chat(ctx, "agent1sender", incoming))
        self.assertEqual(len(ctx.sent), 2)
        self.assertIsInstance(ctx.sent[0][1], ChatAcknowledgement)
        self.assertEqual(ctx.sent[0][1].acknowledged_msg_id, incoming.msg_id)
        reply = ctx.sent[1][1].content[0].text
        self.assertIn("SLO: Reliability target", reply)
        self.assertIn("runbook: Step-by-step incident response guide", reply)
        self.assertIn("Suggested questions", reply)


if __name__ == "__main__":
    unittest.main()
