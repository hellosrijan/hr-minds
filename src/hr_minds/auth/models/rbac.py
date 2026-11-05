from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hr_minds.settings.db import Base, TimestampMixin


class Feature(Base, TimestampMixin):
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    base_path: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    permissions: Mapped[list["Permission"]] = relationship(
        back_populates="feature", cascade="all, delete-orphan"
    )


class Permission(Base, TimestampMixin):
    __table_args__ = (UniqueConstraint("feature_id", "action"),)

    feature_id: Mapped[int] = mapped_column(ForeignKey("feature.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(50))

    feature: Mapped[Feature] = relationship(back_populates="permissions")


class Role(Base, TimestampMixin):
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(default=False)

    # Association table: which permissions each role grants.
    role_permission = Table(
        "role_permission",
        Base.metadata,
        Column("role_id", ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
        Column("permission_id", ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True),
    )

    permissions: Mapped[list[Permission]] = relationship(secondary=role_permission)
