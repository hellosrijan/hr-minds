from fastapi import APIRouter

from hr_minds.media.router import local_media_scan

router = APIRouter()
router.include_router(local_media_scan.router)
