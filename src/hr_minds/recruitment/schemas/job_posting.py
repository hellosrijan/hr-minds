from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from hr_minds.recruitment.models import EmploymentType, JobPostingStatus, WorkMode

MAX_DESCRIPTION_CHARS = 20_000
MAX_SKILLS = 50
MAX_YEARS = 60
CURRENCY_CODE = r"^[A-Z]{3}$"  # ISO 4217, e.g. USD, INR


class JobSkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    must_have: bool = False
    # Years of this skill the job wants; omit it when any experience will do.
    min_years: int | None = Field(default=None, ge=0, le=MAX_YEARS)


class JobSkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    must_have: bool
    min_years: int | None


class JobPostingCreate(BaseModel):
    """Request body for POST /recruitment/job-postings."""

    company_name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    department: str | None = Field(default=None, min_length=1, max_length=100)

    employment_type: EmploymentType = EmploymentType.FULL_TIME
    work_mode: WorkMode = WorkMode.ONSITE
    location_city: str | None = Field(default=None, min_length=1, max_length=100)
    location_region: str | None = Field(default=None, min_length=1, max_length=100)
    location_country: str | None = Field(default=None, min_length=1, max_length=100)

    experience_min_years: int = Field(default=0, ge=0, le=MAX_YEARS)
    experience_max_years: int | None = Field(default=None, ge=0, le=MAX_YEARS)

    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, pattern=CURRENCY_CODE)

    openings: int = Field(default=1, ge=1, le=1000)
    status: JobPostingStatus = JobPostingStatus.OPEN
    skills: list[JobSkillCreate] = Field(default=[], max_length=MAX_SKILLS)


class JobPostingUpdate(BaseModel):
    """Request body for PATCH /recruitment/job-postings/{id}. Omitted fields are unchanged.
    `skills`, if sent, REPLACES the whole list (an empty list clears it). Fields that can be
    empty (department, location, experience_max_years, salary) accept null to clear them."""

    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    department: str | None = Field(default=None, min_length=1, max_length=100)

    employment_type: EmploymentType | None = None
    work_mode: WorkMode | None = None
    location_city: str | None = Field(default=None, min_length=1, max_length=100)
    location_region: str | None = Field(default=None, min_length=1, max_length=100)
    location_country: str | None = Field(default=None, min_length=1, max_length=100)

    experience_min_years: int | None = Field(default=None, ge=0, le=MAX_YEARS)
    experience_max_years: int | None = Field(default=None, ge=0, le=MAX_YEARS)

    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, pattern=CURRENCY_CODE)

    openings: int | None = Field(default=None, ge=1, le=1000)
    status: JobPostingStatus | None = None
    skills: list[JobSkillCreate] | None = Field(default=None, max_length=MAX_SKILLS)


class JobPostingRead(BaseModel):
    id: int
    company_name: str
    title: str
    description: str
    department: str | None
    employment_type: EmploymentType
    work_mode: WorkMode
    location_city: str | None
    location_region: str | None
    location_country: str | None
    experience_min_years: int
    experience_max_years: int | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    openings: int
    status: JobPostingStatus
    created_by_email: str
    skills: list[JobSkillRead]
    created: datetime
    modified: datetime
