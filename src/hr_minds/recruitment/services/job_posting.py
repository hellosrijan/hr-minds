from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.models import Membership
from hr_minds.recruitment.exceptions import InvalidJobPostingRange, JobPostingNotFound
from hr_minds.recruitment.models import JobPosting, JobSkill
from hr_minds.recruitment.schemas import JobPostingCreate, JobPostingRead, JobPostingUpdate, JobSkillCreate, JobSkillRead

# Fields where null is a real value ("clear it"). For the others, null in an update means "leave it alone".
NULLABLE = {
    "department", "location_city", "location_region", "location_country",
    "experience_max_years", "salary_min", "salary_max", "salary_currency",
}


def to_read(posting: JobPosting) -> JobPostingRead:
    """A posting as the API (and the assistant's tools) return it. Needs created_by and skills loaded."""
    return JobPostingRead(
        id=posting.id,
        company_name=posting.company_name,
        title=posting.title,
        description=posting.description,
        department=posting.department,
        employment_type=posting.employment_type,
        work_mode=posting.work_mode,
        location_city=posting.location_city,
        location_region=posting.location_region,
        location_country=posting.location_country,
        experience_min_years=posting.experience_min_years,
        experience_max_years=posting.experience_max_years,
        salary_min=posting.salary_min,
        salary_max=posting.salary_max,
        salary_currency=posting.salary_currency,
        openings=posting.openings,
        status=posting.status,
        created_by_email=posting.created_by.email,
        skills=[JobSkillRead.model_validate(s) for s in posting.skills],
        created=posting.created,
        modified=posting.modified,
    )


def _skill_fields(skill: JobSkillCreate) -> dict:
    return {
        "name": skill.name,
        "name_normalized": skill.name.strip().lower(),
        "must_have": skill.must_have,
        "min_years": skill.min_years,
    }


def _check_ranges(experience_min, experience_max, salary_min, salary_max, currency) -> None:
    """The rules a posting must satisfy whatever the request was, so both create and update call this."""
    if experience_max is not None and experience_max < experience_min:
        raise InvalidJobPostingRange()
    if salary_min is not None and salary_max is not None and salary_max < salary_min:
        raise InvalidJobPostingRange()
    if (salary_min is not None or salary_max is not None) and currency is None:
        raise InvalidJobPostingRange()


async def create(db: AsyncSession, membership: Membership, data: JobPostingCreate) -> JobPosting:
    _check_ranges(data.experience_min_years, data.experience_max_years, data.salary_min, data.salary_max, data.salary_currency)
    posting = JobPosting(
        org_id=membership.org_id,
        created_by_id=membership.user_id,
        **data.model_dump(exclude={"skills"}),
        skills=[JobSkill(**_skill_fields(s)) for s in data.skills],
    )
    db.add(posting)
    await db.commit()
    await db.refresh(posting)  # no attribute_names: a narrower refresh expires the rest
    return posting


async def get(db: AsyncSession, org_id: int, job_posting_id: int) -> JobPosting:
    posting = await JobPosting.get(db, org_id, job_posting_id)
    if posting is None:
        raise JobPostingNotFound()
    return posting


async def list_for_org(db: AsyncSession, org_id: int, page: int = 1, page_size: int = 20) -> tuple[list[JobPosting], int]:
    return await JobPosting.list_for_org(db, org_id, page, page_size)


async def update(db: AsyncSession, org_id: int, job_posting_id: int, data: JobPostingUpdate) -> JobPosting:
    posting = await get(db, org_id, job_posting_id)
    changes = {k: v for k, v in data.model_dump(exclude_unset=True, exclude={"skills"}).items()
               if v is not None or k in NULLABLE}

    # Check the posting as it would be after this change, before anything is written.
    after = {
        "experience_min_years": posting.experience_min_years,
        "experience_max_years": posting.experience_max_years,
        "salary_min": posting.salary_min,
        "salary_max": posting.salary_max,
        "salary_currency": posting.salary_currency,
        **changes,
    }
    _check_ranges(after["experience_min_years"], after["experience_max_years"],
                  after["salary_min"], after["salary_max"], after["salary_currency"])

    for field, value in changes.items():
        setattr(posting, field, value)
    if data.skills is not None:
        await JobPosting.replace_skills(db, posting.id, [_skill_fields(s) for s in data.skills])
    await db.commit()
    # No attribute_names: that form expires the WHOLE object, then reloads only the
    # names given, leaving everything else (e.g. `modified`, created_by) expired and
    # prone to an implicit lazy load outside the async session's context on next access.
    await db.refresh(posting)
    return posting


async def delete(db: AsyncSession, org_id: int, job_posting_id: int) -> None:
    # Skills and candidates go with it via ON DELETE CASCADE.
    posting = await get(db, org_id, job_posting_id)
    await db.delete(posting)
    await db.commit()
