from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hr_minds.settings.db import Base, TimestampMixin


class Feature(Base, TimestampMixin):
    """A module of the app. Rows are synced from settings.features.FEATURES."""

    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    base_path: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    permissions: Mapped[list["Permission"]] = relationship(
        back_populates="feature", cascade="all, delete-orphan", order_by="Permission.id"
    )


class Permission(Base, TimestampMixin):
    """One action on one feature, e.g. media:create."""

    __table_args__ = (UniqueConstraint("feature_id", "action"),)

    feature_id: Mapped[int] = mapped_column(ForeignKey("feature.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(50))

    feature: Mapped[Feature] = relationship(back_populates="permissions", lazy="joined")


class Role(Base, TimestampMixin):
    """A named set of permissions, created by an organization for its members."""

    __table_args__ = (UniqueConstraint("org_id", "name"),)

    # No separate index: the (org_id, name) unique constraint already covers org_id lookups.
    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Association table: which permissions each role grants.
    role_permission = Table(
        "role_permission",
        Base.metadata,
        Column("role_id", ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
        Column("permission_id", ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True),
    )

    # Eager-loaded: async sessions can't lazy-load, and every use needs them.
    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permission, lazy="selectin", order_by=Permission.id
    )

    @classmethod
    async def get(cls, db: AsyncSession, org_id: int, role_id: int) -> "Role | None":
        return await db.scalar(select(cls).where(cls.org_id == org_id, cls.id == role_id))

    @classmethod
    async def list_for_org(cls, db: AsyncSession, org_id: int) -> list["Role"]:
        return list(await db.scalars(select(cls).where(cls.org_id == org_id).order_by(cls.name)))
