from typing import TYPE_CHECKING

from pwdlib import PasswordHash
from sqlalchemy import Column, ForeignKey, String, Table, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hr_minds.auth.exceptions import EmailAlreadyRegistered
from hr_minds.auth.models.rbac import Feature, Permission, Role
from hr_minds.settings.db import Base, TimestampMixin

if TYPE_CHECKING:
    # Imported only for type hints, to avoid a runtime import cycle with schemas.
    from hr_minds.auth.schemas import UserRegister

# Argon2id with library defaults. Shared by all User instances.
_password_hash = PasswordHash.recommended()


class User(Base, TimestampMixin):
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)

    # Associate roles with the user.
    user_role = Table(
        "user_role",
        Base.metadata,
        Column("user_id", ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
        Column("role_id", ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
    )

    roles: Mapped[list[Role]] = relationship(secondary=user_role)

    # --- Password ---

    @staticmethod
    def hash_password(plain: str) -> str:
        """Return an Argon2 hash of `plain`. Store only the hash."""
        return _password_hash.hash(plain)

    @staticmethod
    def check_password_hash(plain: str, hashed: str) -> bool:
        """True if `plain` matches `hashed`. Works without a user instance."""
        return _password_hash.verify(plain, hashed)

    def set_password(self, plain: str) -> None:
        self.password = self.hash_password(plain)

    def check_password(self, plain: str) -> bool:
        """True if `plain` matches this user's stored password."""
        return self.check_password_hash(plain, self.password)

    # --- Queries ---

    @classmethod
    async def register(cls, db: AsyncSession, data: "UserRegister") -> "User":
        """Create a user with a hashed password. Raises EmailAlreadyRegistered on duplicate email."""
        user = cls(
            email=str(data.email).lower(),
            first_name=data.first_name,
            last_name=data.last_name,
        )
        user.set_password(data.password)
        db.add(user)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise EmailAlreadyRegistered from exc
        await db.refresh(user)  # loads server-set created and modified
        return user

    @classmethod
    async def get_by_id(cls, db: AsyncSession, user_id: int) -> "User | None":
        return await db.get(cls, user_id)

    @classmethod
    async def get_by_email(cls, db: AsyncSession, email: str) -> "User | None":
        return await db.scalar(select(cls).where(cls.email == email.lower()))

    async def has_permission(self, db: AsyncSession, feature: str, action: str) -> bool:
        """True if any of this user's roles grants `action` on `feature`."""
        role_permission = Role.role_permission
        stmt = (
            select(literal(1))
            .select_from(self.user_role)
            .join(role_permission, role_permission.c.role_id == self.user_role.c.role_id)
            .join(Permission, Permission.id == role_permission.c.permission_id)
            .join(Feature, Feature.id == Permission.feature_id)
            .where(
                self.user_role.c.user_id == self.id,
                Feature.slug == feature,
                Permission.action == action,
            )
            .limit(1)
        )
        return await db.scalar(stmt) is not None
