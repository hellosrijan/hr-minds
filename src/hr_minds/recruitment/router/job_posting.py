from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.dependencies import require
from hr_minds.auth.models import Membership
from hr_minds.recruitment.models import JobPosting
from hr_minds.recruitment.schemas import JobPostingCreate, JobPostingRead, JobPostingUpdate, JobRequirementRead
from hr_minds.recruitment.services import job_posting as job_posting_service
from hr_minds.settings.db import get_db
from hr_minds.settings.features import FeatureSlug
from hr_minds.utils.pagination import PaginatedResponse

router = APIRouter(prefix="/recruitment/job-postings", tags=["Recruitment"])

RECRUITMENT = FeatureSlug.RECRUITMENT


def _to_read(posting: JobPosting) -> JobPostingRead:
    return JobPostingRead(
        id=posting.id,
        title=posting.title,
        description=posting.description,
        created_by_email=posting.created_by.email,
        requirements=[JobRequirementRead.model_validate(r) for r in posting.requirements],
        created=posting.created,
        modified=posting.modified,
    )


@router.post("", response_model=JobPostingRead, status_code=status.HTTP_201_CREATED, summary="Create a job posting")
async def create_job_posting(
    data: JobPostingCreate,
    membership: Membership = Depends(require(RECRUITMENT, "create")),
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await job_posting_service.create(db, membership, data))


@router.get("", response_model=PaginatedResponse[JobPostingRead], summary="List job postings (paginated)")
async def list_job_postings(
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    membership: Membership = Depends(require(RECRUITMENT, "read")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[JobPostingRead]:
    items, total = await job_posting_service.list_for_org(db, membership.org_id, page, page_size)
    return PaginatedResponse.create(items=[_to_read(p) for p in items], total=total, page=page, page_size=page_size)


@router.get("/{job_posting_id}", response_model=JobPostingRead, summary="Get a job posting")
async def get_job_posting(
    job_posting_id: int,
    membership: Membership = Depends(require(RECRUITMENT, "read")),
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await job_posting_service.get(db, membership.org_id, job_posting_id))


@router.patch("/{job_posting_id}", response_model=JobPostingRead, summary="Update a job posting")
async def update_job_posting(
    job_posting_id: int,
    data: JobPostingUpdate,
    membership: Membership = Depends(require(RECRUITMENT, "update")),
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await job_posting_service.update(db, membership.org_id, job_posting_id, data))


@router.delete(
    "/{job_posting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job posting and its requirements and candidates",
)
async def delete_job_posting(
    job_posting_id: int,
    membership: Membership = Depends(require(RECRUITMENT, "delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await job_posting_service.delete(db, membership.org_id, job_posting_id)
