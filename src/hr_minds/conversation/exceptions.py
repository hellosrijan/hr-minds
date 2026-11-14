from fastapi import HTTPException, status


class ConversationError(HTTPException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Bad request"

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)


class ConversationNotFound(ConversationError):
    # Also what other members get for someone else's conversation: existence isn't leaked.
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Conversation not found"
