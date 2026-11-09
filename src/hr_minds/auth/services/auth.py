from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.exceptions import EmailAlreadyRegistered, InactiveUser, InvalidCredentials
from hr_minds.auth.models import Membership, Organization, User
from hr_minds.auth.schemas import UserRegister

# Checked when the email is unknown, so login takes about the same time either way
DUMMY_HASH = User.hash_password("timing-equalizer-not-a-real-password")


async def register_user(db: AsyncSession, data: UserRegister, is_superuser: bool = False) -> User:
    """
    Create a user plus a personal organization they own, in one transaction.
    Raises EmailAlreadyRegistered on duplicate email.
    """
    user = User(
        email=str(data.email).lower(),
        first_name=data.first_name,
        last_name=data.last_name,
        is_superuser=is_superuser,
    )
    user.set_password(data.password)
    org = Organization(
        public_id=Organization.new_public_id(data.first_name),
        name=data.first_name,
        owner=user,
    )
    db.add_all([user, org, Membership(organization=org, user=user)])
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise EmailAlreadyRegistered from exc
    await db.refresh(user)  # loads server-set created and modified
    return user


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
