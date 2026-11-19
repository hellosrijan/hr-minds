"""
Central API Router Hub.
Aggregates all feature module routers into one root router.
"""

from fastapi import APIRouter

from hr_minds.auth.router import router as auth_router
from hr_minds.conversation.router import router as conversation_router
from hr_minds.media.router import router as media_router
from hr_minds.recruitment.router import router as recruitment_router

api_router = APIRouter(prefix="/api/v1")

# Mount feature module routers
api_router.include_router(auth_router)          # /auth, /orgs, /roles, /members, /invitations, /features
api_router.include_router(media_router)         # /media/local-scans
api_router.include_router(conversation_router)  # /conversations
api_router.include_router(recruitment_router)   # /recruitment/job-postings
