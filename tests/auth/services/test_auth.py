import pytest

from hr_minds.auth.exceptions import EmailAlreadyRegistered, InactiveUser, InvalidCredentials
from hr_minds.auth.models import Membership
from hr_minds.auth.schemas import UserRegister
from hr_minds.auth.services import authenticate_user, register_user

pytestmark = pytest.mark.anyio


def _data(email: str = "Alice@Example.com") -> UserRegister:
    return UserRegister(email=email, first_name="Alice", last_name="Test", password="password123")


async def test_register_creates_user_and_owned_org(db):
    user = await register_user(db, _data())

    assert user.email == "alice@example.com"  # stored lowercase
    assert not user.is_superuser
    membership = await Membership.find(db, user.id)  # no org id = own org
    assert membership.is_owner and membership.role is None
    assert membership.organization.name == "Alice"
    assert membership.organization.public_id.startswith("org_alice_")


async def test_register_rejects_duplicate_email_case_insensitively(db):
    await register_user(db, _data())
    with pytest.raises(EmailAlreadyRegistered):
        await register_user(db, _data("ALICE@example.com"))


async def test_authenticate(db):
    user = await register_user(db, _data())

    assert (await authenticate_user(db, "ALICE@example.com", "password123")).id == user.id
    with pytest.raises(InvalidCredentials):
        await authenticate_user(db, "alice@example.com", "wrong-password")
    with pytest.raises(InvalidCredentials):
        await authenticate_user(db, "nobody@example.com", "password123")


async def test_inactive_user_rejected_only_with_correct_password(db):
    user = await register_user(db, _data())
    user.is_active = False
    await db.commit()

    with pytest.raises(InvalidCredentials):  # wrong password reveals nothing
        await authenticate_user(db, "alice@example.com", "wrong-password")
    with pytest.raises(InactiveUser):
        await authenticate_user(db, "alice@example.com", "password123")
