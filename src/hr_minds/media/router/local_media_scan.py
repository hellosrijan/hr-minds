from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.dependencies import require
from hr_minds.auth.models import Membership
from hr_minds.media.models import LocalMediaScan
from hr_minds.media.schemas import LocalMediaRead, LocalMediaScanCreate, LocalMediaScanRead
from hr_minds.media.services import local_media_scan as local_media_scan_service
from hr_minds.media.services.scanner import scan_stream
from hr_minds.settings.db import get_db
from hr_minds.settings.features import FeatureSlug

router = APIRouter(prefix="/media/local-scans", tags=["Media"])

MEDIA = FeatureSlug.MEDIA


def _to_read(scan: LocalMediaScan) -> LocalMediaScanRead:
    return LocalMediaScanRead(
        id=scan.id,
        name=scan.name,
        folder_path=scan.folder_path,
        hostname=scan.hostname,
        os_name=scan.os_name,
        os_version=scan.os_version,
        created_by_email=scan.created_by.email,
        last_scanned_by_email=scan.last_scanned_by.email if scan.last_scanned_by else None,
        last_scanned_at=scan.last_scanned_at,
        created=scan.created,
        modified=scan.modified,
    )


# One callable per permission so FastAPI caches it: the pre-stream dependencies
# and the endpoint share a single permission check and Membership.
can_create = require(MEDIA, "create")


async def _registered_scan(
    data: LocalMediaScanCreate,
    membership: Membership = Depends(can_create),
    db: AsyncSession = Depends(get_db),
) -> LocalMediaScan:
    # Runs before the SSE stream opens, so a bad folder is a real 422, not a broken stream.
    return await local_media_scan_service.create(db, membership, data)


async def _existing_scan(
    scan_id: int,
    membership: Membership = Depends(can_create),
    db: AsyncSession = Depends(get_db),
) -> LocalMediaScan:
    # Runs before the SSE stream opens, so an unknown id is a real 404.
    return await local_media_scan_service.get(db, membership.org_id, scan_id)


async def _scan_events(
    db: AsyncSession, scan: LocalMediaScan, membership: Membership
) -> AsyncIterable[ServerSentEvent]:
    async for event in scan_stream(db, scan, membership.user):
        yield ServerSentEvent(event=event.pop("event"), data=event)


@router.post(
    "",
    response_class=EventSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a local resume folder and scan it",
)
async def create_scan(
    scan: LocalMediaScan = Depends(_registered_scan),
    membership: Membership = Depends(can_create),
    db: AsyncSession = Depends(get_db),
) -> AsyncIterable[ServerSentEvent]:
    """
    Register a local folder of resumes (pdf, doc, docx, jpg, jpeg, png, webp)
    and immediately scan it. Streams SSE events:
    - `registered` — folder saved, scan starting
    - `progress`   — one event per file found `{file, file_path, media_type, count}`
    - `summary`    — final counts `{total, removed, pdf, document, image}`
    - `error`      — if the folder is no longer readable
    """
    yield ServerSentEvent(event="registered", data=_to_read(scan))
    async for event in _scan_events(db, scan, membership):
        yield event


@router.get("", response_model=list[LocalMediaScanRead], summary="List registered local folders")
async def list_scans(
    membership: Membership = Depends(require(MEDIA, "read")),
    db: AsyncSession = Depends(get_db),
):
    scans = await local_media_scan_service.list_for_org(db, membership.org_id)
    return [_to_read(s) for s in scans]


@router.get("/{scan_id}/files", response_model=list[LocalMediaRead], summary="List resume files in a folder")
async def list_scan_files(
    scan_id: int,
    membership: Membership = Depends(require(MEDIA, "read")),
    db: AsyncSession = Depends(get_db),
):
    return await local_media_scan_service.list_files(db, membership.org_id, scan_id)


@router.post("/{scan_id}/scan", response_class=EventSourceResponse, summary="Re-scan a local folder")
async def rescan(
    scan: LocalMediaScan = Depends(_existing_scan),
    membership: Membership = Depends(can_create),
    db: AsyncSession = Depends(get_db),
) -> AsyncIterable[ServerSentEvent]:
    """
    Re-scan a registered folder: picks up new/changed files and drops deleted ones.
    Same SSE events as create; emits `error` if called from a system other than the folder's.
    """
    async for event in _scan_events(db, scan, membership):
        yield event


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a local folder")
async def delete_scan(
    scan_id: int,
    membership: Membership = Depends(require(MEDIA, "delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a folder and all its discovered files. Files on disk are untouched."""
    await local_media_scan_service.delete(db, membership.org_id, scan_id)
