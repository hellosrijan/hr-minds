from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hr_minds.settings.db import Base, TimestampMixin

if TYPE_CHECKING:
    from hr_minds.auth.models.user import User
    from hr_minds.media.models.local_media import LocalMedia


class LocalMediaScan(Base, TimestampMixin):
    """
    A local folder of candidate resumes registered by a user. The scanner walks
    this path at startup and on demand to populate LocalMedia rows, which
    feed resume analysis and the RAG index.

    The folder lives on the system (hostname/OS) it was registered from, and is
    only ever scanned there — the same path on another machine is a different folder.
    """

    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    folder_path: Mapped[str] = mapped_column(String(1024))
    hostname: Mapped[str] = mapped_column(String(255), index=True)
    os_name: Mapped[str] = mapped_column(String(50))
    os_version: Mapped[str] = mapped_column(String(100))
    # Null when the last scan was the automatic one at app startup.
    last_scanned_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped["User"] = relationship(lazy="joined", foreign_keys=[created_by_id])
    last_scanned_by: Mapped["User | None"] = relationship(lazy="joined", foreign_keys=[last_scanned_by_id])
    files: Mapped[list["LocalMedia"]] = relationship(back_populates="scan", cascade="all, delete-orphan")

    @classmethod
    async def get(cls, db: AsyncSession, org_id: int, scan_id: int) -> "LocalMediaScan | None":
        return await db.scalar(select(cls).where(cls.org_id == org_id, cls.id == scan_id))

    @classmethod
    async def list_for_org(cls, db: AsyncSession, org_id: int) -> list["LocalMediaScan"]:
        return list(await db.scalars(select(cls).where(cls.org_id == org_id).order_by(cls.id)))

    @classmethod
    async def list_for_host(cls, db: AsyncSession, hostname: str) -> list["LocalMediaScan"]:
        """Load all scans across all orgs registered on `hostname` — used by the startup scanner."""
        return list(await db.scalars(select(cls).where(cls.hostname == hostname).order_by(cls.id)))
