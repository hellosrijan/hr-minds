from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hr_minds.settings.db import Base, TimestampMixin

if TYPE_CHECKING:
    from hr_minds.media.models.local_media_scan import LocalMediaScan


class MediaType(StrEnum):
    PDF = "pdf"
    DOCUMENT = "document"
    IMAGE = "image"


# Resume file extensions the scanner picks up. Anything else is ignored.
EXTENSION_MAP: dict[str, MediaType] = {
    ".pdf": MediaType.PDF,
    ".doc": MediaType.DOCUMENT,
    ".docx": MediaType.DOCUMENT,
    ".jpg": MediaType.IMAGE,
    ".jpeg": MediaType.IMAGE,
    ".png": MediaType.IMAGE,
    ".webp": MediaType.IMAGE,
}


class LocalMedia(Base, TimestampMixin):
    """
    A single resume file found by the scanner inside a LocalMediaScan folder.
    Rows are created, refreshed and pruned by the scanner — never by the user.
    `file_modified_at` lets the RAG pipeline re-index only files that changed.
    """

    __table_args__ = (UniqueConstraint("scan_id", "relative_path"),)

    scan_id: Mapped[int] = mapped_column(ForeignKey("local_media_scan.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    # Path relative to the scan's folder_path — preserves subfolder structure.
    relative_path: Mapped[str] = mapped_column(String(1024))
    file_name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[MediaType] = mapped_column(String(20))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    file_modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Eager-loaded so `file_path` works — async sessions can't lazy-load on attribute access.
    # selectin, not joined: one extra `WHERE id IN (...)` query per load instead of
    # repeating the scan (and its two joined users) on every file row.
    scan: Mapped["LocalMediaScan"] = relationship(back_populates="files", lazy="selectin")

    @property
    def file_path(self) -> str:
        """Full path on the scan's system, e.g. /Users/hr/Resumes/2026/jane.pdf or C:\\Resumes\\jane.pdf."""
        return str(Path(self.scan.folder_path) / self.relative_path)

    @classmethod
    async def list_for_scan(cls, db: AsyncSession, scan_id: int) -> list["LocalMedia"]:
        return list(await db.scalars(select(cls).where(cls.scan_id == scan_id).order_by(cls.id)))
