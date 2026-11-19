from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.models.org import Membership
from hr_minds.conversation.agents.registry import tool
from hr_minds.media.schemas import LocalMediaRead
from hr_minds.settings.features import FeatureSlug

from hr_minds.media.services import local_media_scan as media_scan_service

class ListArgs(BaseModel):
    page: int = Field(default=1, ge=1)

@tool(
    name='media_list_resumes',
    description="List the organization's resumes found by folder scans, 20 per page. Each has an id. "
                "Use that id to select the resume for a job posting.",
    args=ListArgs,
    permission=(FeatureSlug.MEDIA, 'read'),
)
async def list_resume(db: AsyncSession, membership: Membership, args: ListArgs) -> dict:
    items, total = await media_scan_service.list_resumes(db, membership, page=args.page)
    return {'total': total, 'items': [LocalMediaRead.model_validate(r).model_dump(mode='json') for r in items]}

