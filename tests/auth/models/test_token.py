from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from hr_minds.auth.models import AccessToken, User
from hr_minds.auth.schemas import UserRegister
from hr_minds.auth.services import register_user

pytestmark = pytest.mark.anyio


def _future(minutes: int = 5) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def test_decode_roundtrip():
    payload = AccessToken.decode(AccessToken._encode("7", "abc", _future()))
    assert payload["sub"] == "7" and payload["jti"] == "abc"


def test_decode_rejects_expired_tampered_and_unsigned_tokens():
    expired = AccessToken._encode("7", "abc", _future(-1))
    tampered = AccessToken._encode("7", "abc", _future())[:-2] + "xx"
    unsigned = jwt.encode({"sub": "7", "jti": "abc", "exp": _future()}, key=None, algorithm="none")

    for token in (expired, tampered, unsigned):
        with pytest.raises(jwt.PyJWTError):
            AccessToken.decode(token)


async def _user(db) -> User:
    return await register_user(db, UserRegister(
        email="alice@example.com", first_name="alice", last_name="Test", password="password123",
    ))


async def test_issue_creates_active_session_until_revoked(db):
    user = await _user(db)
    jti = AccessToken.decode(await AccessToken.issue(db, user))["jti"]

    assert await AccessToken.get_active(db, jti) is not None
    await AccessToken.revoke(db, jti)
    await AccessToken.revoke(db, jti)  # safe twice
    assert await AccessToken.get_active(db, jti) is None


async def test_delete_expired_removes_only_expired_rows(db):
    user = await _user(db)
    db.add_all([
        AccessToken(jti="old", user_id=user.id, expires_at=_future(-1)),
        AccessToken(jti="new", user_id=user.id, expires_at=_future()),
    ])
    await db.commit()

    assert await AccessToken.get_active(db, "old") is None  # expired counts as inactive
    assert await AccessToken.delete_expired(db) == 1
    assert list(await db.scalars(select(AccessToken.jti))) == ["new"]
