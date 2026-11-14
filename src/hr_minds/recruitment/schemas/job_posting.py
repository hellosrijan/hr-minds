from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

MAX_DESCRIPTION_CHARS = 20_000
MAX_REQUIREMENTS = 50


class JobRequirementCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    must_have: bool = False


class JobRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    must_have: bool


class JobPostingCreate(BaseModel):
    """Request body for POST /recruitment/job-postings."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    requirements: list[JobRequirementCreate] = Field(default=[], max_length=MAX_REQUIREMENTS)


class JobPostingUpdate(BaseModel):
    """Request body for PATCH /recruitment/job-postings/{id}. Omitted fields are unchanged.
    `requirements`, if sent, REPLACES the whole list (an empty list clears it)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    requirements: list[JobRequirementCreate] | None = Field(default=None, max_length=MAX_REQUIREMENTS)


class JobPostingRead(BaseModel):
    id: int
    title: str
    description: str
    created_by_email: str
    requirements: list[JobRequirementRead]
    created: datetime
    modified: datetime
