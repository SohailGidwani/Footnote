"""Check the actual chat handler sends an acknowledgement and one text reply."""

import asyncio
import unittest

from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, TextContent

from agent import handle_chat


class FakeContext:
    def __init__(self):
        self.sent = []

    async def send(self, recipient, message):
        self.sent.append((recipient, message))


class ChatProtocolTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
