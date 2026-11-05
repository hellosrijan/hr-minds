"""
Central API Router Hub.
Aggregates all feature module routers into one root router.
"""

from fastapi import APIRouter

from hr_minds.auth.router import router as auth_router

api_router = APIRouter(prefix="/api/v1")

# Mount feature module routers
api_router.include_router(auth_router)
