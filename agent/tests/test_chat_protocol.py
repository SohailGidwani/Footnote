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


if __name__ == "__main__":
    unittest.main()
