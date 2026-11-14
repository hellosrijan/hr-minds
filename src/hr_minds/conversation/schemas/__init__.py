from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

MAX_MESSAGE_CHARS = 20_000


class ConversationCreate(BaseModel):
    """Request body for POST /conversations. `context_type` and `context_id` go together."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    context_type: str | None = Field(default=None, min_length=1, max_length=50)
    context_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def context_comes_as_a_pair(self):
        if (self.context_type is None) != (self.context_id is None):
            raise ValueError("context_type and context_id must be sent together")
        return self


class ConversationUpdate(BaseModel):
    """Request body for PATCH /conversations/{id}."""

    title: str = Field(min_length=1, max_length=255)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    context_type: str | None
    context_id: str | None
    last_message_at: datetime
    created: datetime
    modified: datetime


class MessageCreate(BaseModel):
    """
    Request body for POST /conversations/{id}/messages. Always stored as a `user` message.
    There is no `role` field, and unknown fields are rejected, so a client can't forge
    assistant or tool turns that would later be replayed to the model as history.
    """

    model_config = ConfigDict(extra="forbid")

    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)]


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str | None
    tool_calls: list[dict] | None
    tool_call_id: str | None
    tool_name: str | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    created: datetime
