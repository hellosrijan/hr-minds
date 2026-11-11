from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.dependencies import get_current_user, get_token_payload
from hr_minds.auth.exceptions import EmailAlreadyRegistered, InactiveUser, InvalidCredentials
from hr_minds.auth.models import AccessToken, User
from hr_minds.auth.schemas import AccountDelete, TokenResponse, UserRead, UserRegister
from hr_minds.auth.services import authenticate_user, delete_user, register_user
from hr_minds.settings.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User",
)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Public sign-up. Creates the user and a personal organization they own.
    To join someone else's organization, accept an invitation afterwards.

    - **email**: Valid and unique email address.
    - **first_name**: User's first name (1-100 chars).
    - **last_name**: User's last name (1-100 chars).
    - **password**: Secure password (min 8 chars).

    Raises:
    - **409 Conflict**: If the email is already registered.
    """
    try:
        return await register_user(db, data)
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



@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Delete My Account")
async def delete_me(
    data: AccountDelete,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Permanently delete the current user's account. Confirm with the account password.

    - Memberships in other organizations are removed; those organizations stay as they are.
    - Your own organization is deleted with you, so it must have no other members.

    Raises:
    - **403 Forbidden**: Wrong password.
    - **409 Conflict**: Your organization still has other members.
    """
    try:
        await delete_user(db, user, data.password)
    except InvalidCredentials:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Incorrect password")
