from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.models import Membership
from hr_minds.media.exceptions import LocalMediaScanNotFound, MediaFolderInvalid
from hr_minds.media.models import LocalMedia, LocalMediaScan
from hr_minds.media.schemas import LocalMediaScanCreate
from hr_minds.media.services.scanner import system_info


async def create(db: AsyncSession, membership: Membership, data: LocalMediaScanCreate) -> LocalMediaScan:
    folder = Path(data.folder_path).expanduser().resolve()
    if not folder.is_dir():
        raise MediaFolderInvalid()

    scan = LocalMediaScan(
        org_id=membership.org_id,
        created_by_id=membership.user_id,
        name=data.name,
        folder_path=str(folder),
        **system_info(),
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan, ["created_by"])
    return scan


async def get(db: AsyncSession, org_id: int, scan_id: int) -> LocalMediaScan:
    scan = await LocalMediaScan.get(db, org_id, scan_id)
    if scan is None:
        raise LocalMediaScanNotFound()
    return scan


async def list_for_org(db: AsyncSession, org_id: int) -> list[LocalMediaScan]:
    return await LocalMediaScan.list_for_org(db, org_id)


async def list_files(
    db: AsyncSession,
    org_id: int,
    scan_id: int,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[LocalMedia], int]:
    scan = await get(db, org_id, scan_id)
    return await LocalMedia.list_for_scan(db, scan.id, page=page, page_size=page_size)


async def delete(db: AsyncSession, org_id: int, scan_id: int) -> None:
    scan = await get(db, org_id, scan_id)
    await db.delete(scan)
    await db.commit()
