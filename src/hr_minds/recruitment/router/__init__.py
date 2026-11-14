from fastapi import APIRouter

from hr_minds.recruitment.router import job_candidate, job_posting

router = APIRouter()
router.include_router(job_posting.router)
router.include_router(job_candidate.router)
