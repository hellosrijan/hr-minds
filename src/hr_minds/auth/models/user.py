from pwdlib import PasswordHash
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from hr_minds.settings.db import Base, TimestampMixin

# Argon2id with library defaults. Shared by all User instances.
_password_hash = PasswordHash.recommended()


class User(Base, TimestampMixin):
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)

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
    async def get_by_id(cls, db: AsyncSession, user_id: int) -> "User | None":
        return await db.get(cls, user_id)

    @classmethod
    async def get_by_email(cls, db: AsyncSession, email: str) -> "User | None":
        return await db.scalar(select(cls).where(cls.email == email.lower()))
