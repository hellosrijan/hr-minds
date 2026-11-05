from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.exceptions import InactiveUser, InvalidCredentials
from hr_minds.auth.models import User

# Checked when the email is unknown, so login takes about the same time either way
DUMMY_HASH = User.hash_password("timing-equalizer-not-a-real-password")


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await User.get_by_email(db, email)
    if user is None:
        User.check_password_hash(password, DUMMY_HASH)
        raise InvalidCredentials
    if not user.check_password(password):
        raise InvalidCredentials
    if not user.is_active:
        raise InactiveUser  # checked after the password, so it reveals nothing to strangers
    return user
