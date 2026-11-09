from fastapi import APIRouter

from hr_minds.auth.router import auth, rbac

router = APIRouter()
router.include_router(auth.router)
router.include_router(rbac.router)
