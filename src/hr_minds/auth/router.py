from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.dependencies import get_current_user, get_token_payload, require
from hr_minds.auth.exceptions import EmailAlreadyRegistered, InactiveUser, InvalidCredentials
from hr_minds.auth.models import AccessToken, User
from hr_minds.auth.schemas import TokenResponse, UserRead, UserRegister
from hr_minds.auth.services import authenticate_user
from hr_minds.settings.db import get_db
from hr_minds.settings.features import FeatureSlug

router = APIRouter(prefix="/auth", tags=["Auth"])


# No public sign-up: only superusers or roles granted auth:create can add accounts.
@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User",
    dependencies=[Depends(require(FeatureSlug.AUTH, "create"))],
)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account in the system. Requires the `auth:create` permission (or superuser).

    - **email**: Valid and unique email address.
    - **first_name**: User's first name (1-100 chars).
    - **last_name**: User's last name (1-100 chars).
    - **password**: Secure password (min 8 chars).

    Raises:
    - **401 Unauthorized**: Missing or invalid Bearer token.
    - **403 Forbidden**: Caller lacks the `auth:create` permission.
    - **409 Conflict**: If the email is already registered.
    """
    try:
        return await User.register(db, data)
    except EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")


@router.post("/token", response_model=TokenResponse, summary="Get Access Token (Login)")
async def token(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth2 password flow token endpoint, used by Swagger's Authorize button and API clients (Postman, cURL).

    - **username**: User's email address.
    - **password**: User's password.

    Returns:
    - **access_token**: JWT access token string.
    - **token_type**: Bearer token type.
    """
    try:
        user = await authenticate_user(db, form.username, form.password)
    except InvalidCredentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InactiveUser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    access_token = await AccessToken.issue(db, user)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Logout / Revoke Token")
async def logout(
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Revoke the current access token (JTI blacklist strategy), effectively logging the user out.

    - **Authorization**: Requires Bearer token header.
    - **204 No Content**: Successfully revoked.
    """
    await AccessToken.revoke(db, payload["jti"])


@router.get("/me", response_model=UserRead, summary="Get Current User Profile")
async def me(user: User = Depends(get_current_user)):
    """
    Retrieve the currently authenticated user's public profile data.

    - **Authorization**: Requires Bearer token header.
    """
    return user
