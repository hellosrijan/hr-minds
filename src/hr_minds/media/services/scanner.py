import asyncio
import logging
import platform
import socket
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.models import User
from hr_minds.media.models import EXTENSION_MAP, LocalMedia, LocalMediaScan, MediaType

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def system_info() -> dict[str, str]:
    """
    Identify the machine this process runs on, e.g.
    {"hostname": "srijan-mbp", "os_name": "macOS", "os_version": "15.1"} or
    {"hostname": "HR-PC-02", "os_name": "Windows", "os_version": "11"}.
    """
    # ponytail: hostname is the machine identity; a renamed machine orphans its folders until re-registered
    if platform.system() == "Darwin":
        os_name, os_version = "macOS", platform.mac_ver()[0]
    else:
        os_name, os_version = platform.system(), platform.release()
    return {"hostname": socket.gethostname(), "os_name": os_name, "os_version": os_version}


def _walk(scan: LocalMediaScan) -> list[dict]:
    """Collect a row for every supported resume file under the scan folder. Blocking I/O."""
    root = Path(scan.folder_path)
    rows: list[dict] = []
    for path in root.rglob("*"):
        media_type = EXTENSION_MAP.get(path.suffix.lower())
        if media_type is None or not path.is_file():
            continue
        stat = path.stat()
        rows.append(
            {
                "scan_id": scan.id,
                "org_id": scan.org_id,
                "relative_path": str(path.relative_to(root)),
                "file_name": path.name,
                "media_type": media_type,
                "file_size_bytes": stat.st_size,
                "file_modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            }
        )
    return rows


async def _upsert(db: AsyncSession, rows: list[dict]) -> None:
    stmt = insert(LocalMedia).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["scan_id", "relative_path"],
        set_={
            "file_size_bytes": stmt.excluded.file_size_bytes,
            "file_modified_at": stmt.excluded.file_modified_at,
        },
    )
    await db.execute(stmt)
    await db.commit()


async def scan_stream(
    db: AsyncSession, scan: LocalMediaScan, scanned_by: User | None = None
) -> AsyncGenerator[dict, None]:
    """
    Walk `scan.folder_path` recursively, upsert LocalMedia rows in batches,
    drop rows for files that no longer exist, record who scanned and when,
    and yield progress events for SSE:

      {"event": "progress", "file": "<relative path>", "file_path": "<full path>", "media_type": "<type>", "count": N}
      {"event": "summary",  "total": N, "removed": N, "pdf": N, "document": N, "image": N,
                            "hostname": "...", "os_name": "...", "os_version": "...", "scanned_by_email": "..."}
      {"event": "error",    "detail": "<message>"}

    Only runs on the system the folder was registered on. `scanned_by` is None for the startup scan.
    Safe to call repeatedly — keyed on (scan_id, relative_path), so re-scans never duplicate.
    """
    hostname = socket.gethostname()
    if scan.hostname != hostname:
        yield {"event": "error", "detail": f"Folder is on {scan.hostname}; this system is {hostname}"}
        return

    if not Path(scan.folder_path).is_dir():
        logger.warning("LocalMediaScan id=%d path invalid: %s", scan.id, scan.folder_path)
        yield {"event": "error", "detail": f"Folder not found: {scan.folder_path}"}
        return

    rows = await asyncio.to_thread(_walk, scan)
    counts: dict[str, int] = {t: 0 for t in MediaType}
    root = Path(scan.folder_path)

    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        await _upsert(db, batch)
        for i, row in enumerate(batch, start + 1):
            counts[row["media_type"]] += 1
            yield {
                "event": "progress",
                "file": row["relative_path"],
                "file_path": str(root / row["relative_path"]),
                "media_type": row["media_type"],
                "count": i,
            }

    # ponytail: NOT IN with every found path; switch to a scan-run marker column if folders reach ~100k files
    result = await db.execute(
        delete(LocalMedia).where(
            LocalMedia.scan_id == scan.id,
            LocalMedia.relative_path.notin_([r["relative_path"] for r in rows]),
        )
    )
    # The OS can be upgraded between scans; the hostname stays the folder's identity.
    info = system_info()
    scan.os_name, scan.os_version = info["os_name"], info["os_version"]
    scan.last_scanned_by = scanned_by
    scan.last_scanned_at = func.now()
    await db.commit()
    await db.refresh(scan, ["last_scanned_at"])

    scanned_by_email = scanned_by.email if scanned_by else None
    logger.info(
        "LocalMediaScan id=%d: %d files, %d removed, from %s on %s (%s %s) by %s",
        scan.id, len(rows), result.rowcount, scan.folder_path,
        scan.hostname, scan.os_name, scan.os_version, scanned_by_email or "startup",
    )
    yield {
        "event": "summary",
        "total": len(rows),
        "removed": result.rowcount,
        **counts,
        "hostname": scan.hostname,
        "os_name": scan.os_name,
        "os_version": scan.os_version,
        "scanned_by_email": scanned_by_email,
    }


async def scan_all(db: AsyncSession) -> None:
    """Re-scan every local folder registered on this system. Called at app startup."""
    scans = await LocalMediaScan.list_for_host(db, socket.gethostname())
    if not scans:
        logger.info("No local media scans registered on this system — skipping startup scan")
        return

    logger.info("Starting local media scan for %d folder(s)", len(scans))
    for scan in scans:
        async for _ in scan_stream(db, scan):
            pass
