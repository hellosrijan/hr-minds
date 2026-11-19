from hr_minds.settings.llm import LLM, Capability, LLMNotConfigured, LLMReply


class FakeLLM(LLM):
    """Scripted stand-in for tests: returns the given replies in order and records what it was sent."""

    def __init__(self, replies: list[LLMReply]):
        self.replies = list(replies)
        self.calls: list[list[dict]] = []

    async def chat(
        self, messages: list[dict], tools: list[dict], capability: Capability = "default"
    ) -> LLMReply:
        self.calls.append(list(messages))
        return self.replies.pop(0)


class UnconfiguredLLM(LLM):
    """What tests get by default: the assistant never answers, so only user messages are stored."""

    async def chat(
        self, messages: list[dict], tools: list[dict], capability: Capability = "default"
    ) -> LLMReply:
        raise LLMNotConfigured()

class ScriptedModel:
    """Stands in for the chat model in loop tests: gives the scripted replies in order and records what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.sent: list[list] = []

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages, **kwargs):
        self.sent.append(list(messages))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
