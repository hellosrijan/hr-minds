"""The recruitment module's tools for the assistant. Importing this module registers them."""

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.models import Membership
from hr_minds.conversation.agents.registry import tool
from hr_minds.recruitment.models.job_candidate import JobCandidateStatus
from hr_minds.recruitment.schemas import JobPostingCreate, JobPostingUpdate
from hr_minds.recruitment.schemas.job_candidate import JobCandidateCreate, JobCandidateUpdate
from hr_minds.recruitment.services import job_posting as job_posting_service
from hr_minds.recruitment.services import job_candidate as job_candidate_service
from hr_minds.settings.features import FeatureSlug


class ListArgs(BaseModel):
    page: int = Field(default=1, ge=1)


class PostingIdArgs(BaseModel):
    job_posting_id: int


class UpdateArgs(JobPostingUpdate):
    job_posting_id: int

class SelectArgs(BaseModel):
    job_posting_id: int
    local_media_id: int


class CandidateStatusArgs(BaseModel):
    job_posting_id: int
    candidate_id: int
    status: JobCandidateStatus

@tool(
    name="recruitment_list_job_postings",
    description="List the organization's job postings, 20 per page. Use when the user asks what jobs exist.",
    args=ListArgs,
    permission=(FeatureSlug.RECRUITMENT, "read"),
)
async def list_job_postings(db: AsyncSession, membership: Membership, args: ListArgs) -> dict:
    items, total = await job_posting_service.list_for_org(db, membership.org_id, page=args.page)
    return {"total": total, "items": [job_posting_service.to_read(p).model_dump(mode="json") for p in items]}


@tool(
    name="recruitment_get_job_posting",
    description="Get one job posting by its id, with its company, location, experience, skills and salary.",
    args=PostingIdArgs,
    permission=(FeatureSlug.RECRUITMENT, "read"),
)
async def get_job_posting(db: AsyncSession, membership: Membership, args: PostingIdArgs) -> dict:
    posting = await job_posting_service.get(db, membership.org_id, args.job_posting_id)
    return job_posting_service.to_read(posting).model_dump(mode="json")


@tool(
    name="recruitment_create_job_posting",
    description="Create a job posting: the company, title and description, employment type and work mode, "
                "location (city, region, country), the years of experience wanted, skills (each must_have or not, "
                "with optional min_years), and salary if known. Leave out what the user did not give. "
                "The user must approve it before it is saved.",
    args=JobPostingCreate,
    permission=(FeatureSlug.RECRUITMENT, "create"),
    requires_approval=True,
)
async def create_job_posting(db: AsyncSession, membership: Membership, args: JobPostingCreate) -> dict:
    posting = await job_posting_service.create(db, membership, args)
    return job_posting_service.to_read(posting).model_dump(mode="json")


@tool(
    name="recruitment_update_job_posting",
    description="Change a job posting by id. Send only the fields that change. Sending skills replaces the whole list. "
                "The user must approve it before it is saved.",
    args=UpdateArgs,
    permission=(FeatureSlug.RECRUITMENT, "update"),
    requires_approval=True,
)
async def update_job_posting(db: AsyncSession, membership: Membership, args: UpdateArgs) -> dict:
    data = JobPostingUpdate(**args.model_dump(exclude={"job_posting_id"}, exclude_unset=True))
    posting = await job_posting_service.update(db, membership.org_id, args.job_posting_id, data)
    return job_posting_service.to_read(posting).model_dump(mode="json")

@tool(
    name="recruitment_select_candidate",
    description="Select a resume for a job posting. Use the job posting id and the resume id from "
                "media_list_resumes. The user must approve it before it is saved.",
    args=SelectArgs,
    permission=(FeatureSlug.RECRUITMENT, "create"),
    requires_approval=True,
)
async def select_candidate(db: AsyncSession, membership: Membership, args: SelectArgs) -> dict:
    candidate = await job_candidate_service.select(
        db, membership, args.job_posting_id, JobCandidateCreate(local_media_id=args.local_media_id)
    )
    return job_candidate_service.to_read(candidate).model_dump(mode="json")


@tool(
    name="recruitment_update_candidate_status",
    description="Move a candidate to a new pipeline status: shortlisted, interviewing, offered, hired or rejected. "
                "The user must approve it before it is saved.",
    args=CandidateStatusArgs,
    permission=(FeatureSlug.RECRUITMENT, "update"),
    requires_approval=True,
)
async def update_candidate_status(db: AsyncSession, membership: Membership, args: CandidateStatusArgs) -> dict:
    candidate = await job_candidate_service.update_status(
        db, membership.org_id, args.job_posting_id, args.candidate_id, JobCandidateUpdate(status=args.status)
    )
    return job_candidate_service.to_read(candidate).model_dump(mode="json")
