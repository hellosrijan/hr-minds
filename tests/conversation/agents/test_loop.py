"""
Tests for the LangGraph loop in agents/loop.py. The model is a scripted fake, so nothing
calls a real LLM. Each test sends a message through the real endpoint and checks what the
model was sent and what was saved.
"""

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel

from hr_minds.conversation.agents import registry
from hr_minds.conversation.agents.loop import MAX_STEPS, _without_broken_tool_exchanges, get_chat_model
from hr_minds.conversation.models import Message, MessageRole
from hr_minds.main import app
from hr_minds.settings.features import FeatureSlug
from tests.fake_llm import ScriptedModel
from tests.media.router.test_local_media_scan import sse_events

CONVERSATIONS = "/api/v1/conversations"


class LookupArgs(BaseModel):
    title: str


if not registry.get("loop_lookup_posting"):
    @registry.tool(
        name="loop_lookup_posting",
        description="Look up a job posting by title",
        args=LookupArgs,
        permission=(FeatureSlug.CONVERSATION, "create"),
    )
    async def loop_lookup_posting(db, membership, args: LookupArgs):
        return {"id": 1, "title": args.title}


def asks_for_tool(call_id: str, title: str = "Backend") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"id": call_id, "name": "loop_lookup_posting", "args": {"title": title}}])


@pytest.fixture
def use_model():
    """Send the chat endpoint to a fake model for one test."""

    def _use(model):
        app.dependency_overrides[get_chat_model] = lambda: model

    yield _use
    app.dependency_overrides.pop(get_chat_model, None)


async def start(client, headers) -> int:
    r = await client.post(CONVERSATIONS, json={}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def send(client, headers, cid, content) -> list[tuple[str, dict]]:
    r = await client.post(f"{CONVERSATIONS}/{cid}/messages", json={"content": content}, headers=headers)
    assert r.status_code == 200, r.text
    return sse_events(r.text)


@pytest.mark.anyio
async def test_plain_answer_ends_the_turn(client, signup, use_model):
    headers, _ = await signup("alice")
    cid = await start(client, headers)
    use_model(ScriptedModel(AIMessage(content="Hello, how can I help?")))

    events = await send(client, headers, cid, "hi")

    assert [name for name, _ in events] == ["message", "message", "done"]
    assert events[1][1]["content"] == "Hello, how can I help?"
    stored = (await client.get(f"{CONVERSATIONS}/{cid}/messages", headers=headers)).json()["items"]
    assert [m["role"] for m in stored] == ["user", "assistant"]


@pytest.mark.anyio
async def test_tool_round_trip(client, signup, use_model):
    headers, _ = await signup("alice")
    cid = await start(client, headers)
    model = ScriptedModel(asks_for_tool("call_1"), AIMessage(content="Found it."))
    use_model(model)

    events = await send(client, headers, cid, "Find the backend posting")

    assert [name for name, _ in events] == ["message", "tool_call", "tool_result", "message", "done"]
    assert events[1][1]["tool_calls"][0]["name"] == "loop_lookup_posting"
    assert events[2][1]["tool_call_id"] == "call_1"
    assert "Backend" in events[2][1]["content"]
    assert events[3][1]["content"] == "Found it."
    # The second model call received the tool's result as the last message.
    assert isinstance(model.sent[1][-1], ToolMessage)


@pytest.mark.anyio
async def test_history_grows_by_one_exchange_per_turn(client, signup, use_model):
    headers, _ = await signup("alice")
    cid = await start(client, headers)
    model = ScriptedModel(AIMessage(content="one"), AIMessage(content="two"), AIMessage(content="three"))
    use_model(model)

    for text in ("first", "second", "third"):
        await send(client, headers, cid, text)

    # System prompt plus every earlier message plus this one: 2, then 4, then 6. Never more.
    assert [len(sent) for sent in model.sent] == [2, 4, 6]


@pytest.mark.anyio
async def test_a_model_that_never_stops_asking_for_tools_is_cut_off(client, signup, use_model):
    headers, _ = await signup("alice")
    cid = await start(client, headers)
    model = ScriptedModel(*[asks_for_tool(f"call_{i}") for i in range(MAX_STEPS + 5)])
    use_model(model)

    events = await send(client, headers, cid, "loop forever")

    assert events[-1] == ("error", {"detail": f"Stopped after {MAX_STEPS} steps without a final answer."})
    assert len(model.sent) == MAX_STEPS


@pytest.mark.anyio
async def test_a_failing_model_keeps_the_user_message(client, signup, use_model):
    headers, _ = await signup("alice")
    cid = await start(client, headers)
    use_model(ScriptedModel(RuntimeError("provider is down")))

    events = await send(client, headers, cid, "hello?")

    assert [name for name, _ in events] == ["message", "error"]
    assert events[1][1]["detail"] == "The assistant failed to answer."
    stored = (await client.get(f"{CONVERSATIONS}/{cid}/messages", headers=headers)).json()["items"]
    assert [m["role"] for m in stored] == ["user"]


@pytest.mark.anyio
async def test_unconfigured_assistant_only_saves_the_user_message(client, signup):
    headers, _ = await signup("alice")
    cid = await start(client, headers)

    events = await send(client, headers, cid, "hello?")

    assert [name for name, _ in events] == ["message", "error"]
    assert events[1][1]["detail"] == "The assistant is not configured."


def test_history_skips_a_tool_call_that_never_got_its_result():
    asked = Message(role=MessageRole.ASSISTANT, content=None, tool_calls=[{"id": "call_1", "name": "x", "arguments": {}}])

    kept = _without_broken_tool_exchanges([
        Message(role=MessageRole.USER, content="first"),
        asked,
        Message(role=MessageRole.USER, content="second"),
    ])

    assert [m.content for m in kept] == ["first", "second"]


@pytest.mark.anyio
async def test_current_time_tool(client, signup, use_model):
    headers, _ = await signup("alice")
    cid = await start(client, headers)
    use_model(ScriptedModel(
        AIMessage(content="", tool_calls=[{"id": "call_t", "name": "conversation_current_time", "args": {}}]),
        AIMessage(content="It is now."),
    ))

    events = await send(client, headers, cid, "What time is it?")
    assert [name for name, _ in events] == ["message", "tool_call", "tool_result", "message", "done"]
    assert "now" in events[2][1]["content"]

