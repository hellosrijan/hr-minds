import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import jwt
from sqlalchemy import DateTime, ForeignKey, String, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from hr_minds.settings.config import settings
from hr_minds.settings.db import Base

if TYPE_CHECKING:
    from hr_minds.auth.models.user import User


class AccessToken(Base):
    """
    One row per issued access token. The row is the session: logout sets
    `revoked_at`, and expired rows are removed by `delete_expired`.
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # --- JWT (stateless part) ---

    @staticmethod
    def _encode(subject: str, jti: str, expires_at: datetime) -> str:
        payload = {"sub": subject, "exp": expires_at, "jti": jti}
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def decode(token: str) -> dict:
        """Verify signature and expiry. Raises jwt.PyJWTError if invalid."""
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    # --- Database ---

    @classmethod
    async def issue(cls, db: AsyncSession, user: "User") -> str:
        """Insert a session row for `user` and return the signed JWT for it."""
        jti = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        db.add(cls(jti=jti, user_id=user.id, expires_at=expires_at))
        await db.commit()
        return cls._encode(str(user.id), jti, expires_at)

    @classmethod
    async def get_active(cls, db: AsyncSession, jti: str) -> "AccessToken | None":
        """Return the row only if it exists, is not revoked, and has not expired."""
        return await db.scalar(
            select(cls).where(
                cls.jti == jti,
                cls.revoked_at.is_(None),
                cls.expires_at > func.now(),
            )
        )

    @classmethod
    async def revoke(cls, db: AsyncSession, jti: str) -> None:
        """Mark the session as revoked. Safe to call twice."""
        row = await db.scalar(select(cls).where(cls.jti == jti))
        if row is not None and row.revoked_at is None:
            row.revoked_at = func.now()
            await db.commit()

    @classmethod
    async def delete_expired(cls, db: AsyncSession) -> int:
        """Remove rows whose expiry has passed. Returns the number deleted."""
        result = await db.execute(delete(cls).where(cls.expires_at < func.now()))
        await db.commit()
        return result.rowcount
