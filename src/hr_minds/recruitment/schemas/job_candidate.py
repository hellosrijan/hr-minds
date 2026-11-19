from datetime import datetime

from pydantic import BaseModel

from hr_minds.media.schemas import LocalMediaRead
from hr_minds.recruitment.models import JobCandidateStatus


class JobCandidateCreate(BaseModel):
    """Request body for POST .../candidates: select one resume for this job posting."""

    local_media_id: int


class JobCandidateUpdate(BaseModel):
    """Request body for PATCH .../candidates/{id}: move it to a new pipeline status."""

    status: JobCandidateStatus


class JobCandidateRead(BaseModel):
    id: int
    status: JobCandidateStatus
    resume: LocalMediaRead
    selected_by_email: str | None
    created: datetime
    modified: datetime
