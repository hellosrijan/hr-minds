from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from hr_minds.utils.pagination import PaginatedResponse


class LocalMediaScanCreate(BaseModel):
    """Request body for POST /media/local-scans."""

    name: str = Field(min_length=1, max_length=255)
    folder_path: str = Field(min_length=1, max_length=1024)


class LocalMediaScanRead(BaseModel):
    """Response body for a single registered local folder."""

    id: int
    name: str
    folder_path: str
    hostname: str
    os_name: str
    os_version: str
    created_by_email: str
    last_scanned_by_email: str | None
    last_scanned_at: datetime | None
    created: datetime
    modified: datetime


class LocalMediaRead(BaseModel):
    """Response body for a single discovered resume file."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_id: int
    file_name: str
    relative_path: str
    file_path: str
    media_type: str
    file_size_bytes: int
    file_modified_at: datetime
    created: datetime
