import hashlib
import re
import secrets
import string
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hr_minds.auth.models.rbac import Role
from hr_minds.settings.db import Base, TimestampMixin

if TYPE_CHECKING:
    from hr_minds.auth.models.user import User


_ID_ALPHABET = string.ascii_lowercase + string.digits


class Organization(Base, TimestampMixin):
    """
    A tenant. Every user gets one at signup and is its owner.

    `id` stays internal (foreign keys); clients only see and send `public_id`.
    """

    public_id: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)

    owner: Mapped["User"] = relationship()

    @staticmethod
    def new_public_id(name: str) -> str:
        """
        "Apple" -> "org_apple_k3x9p2m7qa". Set once at creation; a later rename
        doesn't change it, so stored IDs keep working.
        """
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", ""))
        slug = slug.strip("-")[:30].strip("-") or "org"
        # 36^10 values; the unique constraint catches the (negligible) collision.
        suffix = "".join(secrets.choice(_ID_ALPHABET) for _ in range(10))
        return f"org_{slug}_{suffix}"


class Membership(Base, TimestampMixin):
    """A user's place in an organization. The owner has no role; owners can do everything."""

    __table_args__ = (UniqueConstraint("org_id", "user_id"),)

    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    # RESTRICT: a role still assigned to members can't be deleted.
    role_id: Mapped[int | None] = mapped_column(
        ForeignKey("role.id", ondelete="RESTRICT"), nullable=True
    )

    organization: Mapped[Organization] = relationship(lazy="joined")
    user: Mapped["User"] = relationship(lazy="joined")
    role: Mapped[Role | None] = relationship(lazy="joined")

    @property
    def is_owner(self) -> bool:
        return self.organization.owner_id == self.user_id

    def grants(self) -> set[tuple[str, str]]:
        """(feature, action) pairs this member's role grants. Empty for the owner; use can()."""
        if self.role is None:
            return set()
        return {(p.feature.slug, p.action) for p in self.role.permissions}

    def can(self, feature: str, action: str) -> bool:
        return self.is_owner or (feature, action) in self.grants()

    @classmethod
    async def get(cls, db: AsyncSession, org_id: int, user_id: int) -> "Membership | None":
        return await db.scalar(select(cls).where(cls.org_id == org_id, cls.user_id == user_id))

    @classmethod
    async def find(
        cls, db: AsyncSession, user_id: int, org_public_id: str | None = None
    ) -> "Membership | None":
        """The user's membership in org `org_public_id`, or in the org they own when None."""
        stmt = select(cls).join(Organization, Organization.id == cls.org_id).where(cls.user_id == user_id)
        if org_public_id is None:
            stmt = stmt.where(Organization.owner_id == user_id)
        else:
            stmt = stmt.where(Organization.public_id == org_public_id)
        return await db.scalar(stmt)

    @classmethod
    async def list_for_org(cls, db: AsyncSession, org_id: int) -> list["Membership"]:
        return list(await db.scalars(select(cls).where(cls.org_id == org_id).order_by(cls.id)))

    @classmethod
    async def list_for_user(cls, db: AsyncSession, user_id: int) -> list["Membership"]:
        return list(await db.scalars(select(cls).where(cls.user_id == user_id).order_by(cls.id)))


class Invitation(Base, TimestampMixin):
    """
    An offer to join an organization with a given role. Only the SHA-256 of the
    token is stored, so a database leak doesn't expose usable invite links.
    """

    org_id: Mapped[int] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[int] = mapped_column(ForeignKey("role.id", ondelete="CASCADE"))
    # SET NULL: an invitation stays valid if the person who sent it deletes their account.
    invited_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    role: Mapped[Role] = relationship(lazy="joined")

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    async def get_pending(cls, db: AsyncSession, token: str) -> "Invitation | None":
        """Return the invitation only if it is unused and not expired."""
        return await db.scalar(
            select(cls).where(
                cls.token_hash == cls.hash_token(token),
                cls.accepted_at.is_(None),
                cls.expires_at > func.now(),
            )
        )
