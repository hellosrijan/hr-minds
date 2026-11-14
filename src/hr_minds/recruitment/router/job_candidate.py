from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.dependencies import require
from hr_minds.auth.models import Membership
from hr_minds.media.schemas import LocalMediaRead
from hr_minds.recruitment.models import JobCandidate, JobCandidateStatus
from hr_minds.recruitment.schemas import JobCandidateCreate, JobCandidateRead, JobCandidateUpdate
from hr_minds.recruitment.services import job_candidate as job_candidate_service
from hr_minds.settings.db import get_db
from hr_minds.settings.features import FeatureSlug
from hr_minds.utils.pagination import PaginatedResponse

router = APIRouter(prefix="/recruitment/job-postings/{job_posting_id}/candidates", tags=["Recruitment"])

RECRUITMENT = FeatureSlug.RECRUITMENT


def _to_read(candidate: JobCandidate) -> JobCandidateRead:
    return JobCandidateRead(
        id=candidate.id,
        status=candidate.status,
        resume=LocalMediaRead.model_validate(candidate.resume),
        selected_by_email=candidate.selected_by.email if candidate.selected_by else None,
        created=candidate.created,
        modified=candidate.modified,
    )


@router.post("", response_model=JobCandidateRead, status_code=status.HTTP_201_CREATED,
            summary="Select a resume for this job posting")
async def select_candidate(
    job_posting_id: int,
    data: JobCandidateCreate,
    membership: Membership = Depends(require(RECRUITMENT, "create")),
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await job_candidate_service.select(db, membership, job_posting_id, data))


@router.get("", response_model=PaginatedResponse[JobCandidateRead],
           summary="List candidates selected for this job posting (paginated)")
async def list_candidates(
    job_posting_id: int,
    status_filter: Annotated[JobCandidateStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    membership: Membership = Depends(require(RECRUITMENT, "read")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[JobCandidateRead]:
    items, total = await job_candidate_service.list_for_posting(
        db, membership.org_id, job_posting_id, page, page_size, status_filter
    )
    return PaginatedResponse.create(items=[_to_read(c) for c in items], total=total, page=page, page_size=page_size)


@router.patch("/{candidate_id}", response_model=JobCandidateRead, summary="Change a candidate's pipeline status")
async def update_candidate(
    job_posting_id: int,
    candidate_id: int,
    data: JobCandidateUpdate,
    membership: Membership = Depends(require(RECRUITMENT, "update")),
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await job_candidate_service.update_status(db, membership.org_id, job_posting_id, candidate_id, data))


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT,
              summary="Remove a candidate from the pipeline (the resume file is untouched)")
async def remove_candidate(
    job_posting_id: int,
    candidate_id: int,
    membership: Membership = Depends(require(RECRUITMENT, "delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await job_candidate_service.remove(db, membership.org_id, job_posting_id, candidate_id)
