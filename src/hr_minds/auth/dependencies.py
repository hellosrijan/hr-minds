import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.exceptions import OrganizationNotFound, Unauthorized
from hr_minds.auth.models import AccessToken, Membership, User
from hr_minds.settings.db import get_db

# tokenUrl must match the OAuth2 token endpoint. Swagger's Authorize button uses it.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


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
    Allow the request if the user is the owner of, or holds a role granting
    `action` on `feature` in, the organization named by the `X-Org-Id` header
    (a public id like org_srijan_k3x9p2m7qa). Without the header, the user's
    own organization is used. Returns the caller's Membership.
    Non-members get 404, members without the permission 403.

    Usage: membership: Membership = Depends(require(FeatureSlug.ROLES, "read"))
    """

    async def checker(
        x_org_id: str | None = Header(default=None, description="Organization public id; defaults to your own"),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Membership:
        membership = await Membership.find(db, user.id, x_org_id)
        if membership is None:
            raise OrganizationNotFound()
        if not membership.can(feature, action):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
        return membership

    return checker
