from fastapi import APIRouter

from hr_minds.conversation.router import conversation

router = APIRouter()
router.include_router(conversation.router)
