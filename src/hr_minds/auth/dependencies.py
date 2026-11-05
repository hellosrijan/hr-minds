import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.exceptions import Unauthorized
from hr_minds.auth.models import AccessToken, User
from hr_minds.settings.db import get_db

# tokenUrl must match the OAuth2 token endpoint. Swagger's Authorize button uses it.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_token_payload(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify the JWT, then confirm the session row is still active."""
    try:
        payload = AccessToken.decode(token)
    except jwt.PyJWTError:
        raise Unauthorized()

    jti = payload.get("jti")
    if not jti or await AccessToken.get_active(db, jti) is None:
        raise Unauthorized("Session is revoked or expired")
    return payload


async def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Load the user the token belongs to. Rejects inactive or deleted users."""
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise Unauthorized()

    user = await User.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("User is inactive or no longer exists")
    return user


def require(feature: str, action: str):
    """
    Allow the request if the user is a superuser, or holds a role that
    grants `action` on `feature`. Otherwise respond 403.

    Usage: dependencies=[Depends(require("media", "create"))]
    """

    async def checker(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if user.is_superuser:
            return user

        if not await user.has_permission(db, feature, action):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
        return user

    return checker
