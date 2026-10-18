"""Local Fetch.ai mailbox agent for the Footnote glossary and digest."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from footnote import answer_text, load_pack


HERE = Path(__file__).resolve().parent


def load_local_env() -> None:
    path = HERE / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()
backend_url = os.getenv("BACKEND_URL", "http://localhost:8000").strip()
pack = load_pack()


async def handle_chat(ctx: Context, sender: str, message: ChatMessage) -> None:
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=message.msg_id))
    question = " ".join(item.text for item in message.content if isinstance(item, TextContent))
    try:
        reply = await asyncio.to_thread(answer_text, question, pack, backend_url)
    except Exception:
        ctx.logger.exception("Could not answer chat message")
        reply = "I could not answer that right now. Please try again."
    await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text=reply)]))


async def handle_acknowledgement(ctx: Context, sender: str, message: ChatAcknowledgement) -> None:
    ctx.logger.debug("Chat reply acknowledged")


def build_agent() -> Agent:
    seed = os.getenv("AGENT_SEED", "").strip()
    if not seed or seed == "replace-with-a-long-random-secret-and-keep-it-private":
        raise RuntimeError("Set a private AGENT_SEED in the ignored agent/.env file before running")
    agent = Agent(
        name="Footnote Jargon Decoder",
        handle="footnote-jargon-decoder",
        description=(
            "Explains Halcyon company jargon, recalls terms learned in Footnote meetings, "
            "prepares you for meetings, and suggests teammates to contact."
        ),
        seed=seed,
        port=8001,
        mailbox=True,
        publish_agent_details=True,
        readme_path=str(HERE / "README.md"),
    )
    chat = Protocol(spec=chat_protocol_spec)
    chat.on_message(ChatMessage)(handle_chat)
    chat.on_message(ChatAcknowledgement)(handle_acknowledgement)
    agent.include(chat, publish_manifest=True)
    return agent


if __name__ == "__main__":
    build_agent().run()
