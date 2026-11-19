"""The conversation module's own tools."""

from datetime import datetime, timezone

from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.models import Membership
from hr_minds.conversation.agents.registry import tool
from hr_minds.settings.features import FeatureSlug

class NoArgs(BaseModel):
    ...

@tool(
    name="conversation_current_time",
    description="Get the current date and time in UTC. Use when the user asks what time or date it is.",
    args=NoArgs,
    permission=(FeatureSlug.CONVERSATION, "read"),
)
async def current_time(db: AsyncSession, membership: Membership, args: NoArgs) -> dict:
    return {"now": datetime.now(timezone.utc).isoformat()}