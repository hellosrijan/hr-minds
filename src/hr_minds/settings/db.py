"""
Database setup for HR Minds API.

Provides the async SQLAlchemy engine, the session factory, the declarative
Base (with a naming convention for Alembic), a TimestampMixin for shared
columns, and the get_db() FastAPI dependency.
"""

import re
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from hr_minds.settings.config import settings

# Async engine. Connects to PostgreSQL using settings.DATABASE_URL.
# echo=True logs every SQL statement when DEBUG is enabled.
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)

# Factory for new async sessions. expire_on_commit=False keeps loaded
# objects usable after commit, which avoids extra queries in async code.
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Predictable constraint names. Alembic needs stable names to drop or
# rename constraints later; without this, PostgreSQL picks them for you.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Declarative base class for all ORM models.

    Every model inherits from Base. The table name is generated from the
    class name (User -> user, SelectedCandidate -> selected_candidate).
    Base.metadata holds the table definitions that Alembic uses.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    @declared_attr.directive
    def __tablename__(cls) -> str:
        # "SelectedCandidate" -> "selected_candidate"
        return re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={getattr(self, 'id', None)}>"


class TimestampMixin:
    """
    Shared columns: integer primary key and created/modified timestamps.
    Add it to a model with: class User(Base, TimestampMixin): ...
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    modified: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields one database session per request.

    The session is closed automatically when the request finishes.
    Usage:
        async def endpoint(db: AsyncSession = Depends(get_db)): ...
    """
    async with AsyncSessionLocal() as session:
        yield session
