# Media (Local Resume Scanner)

Code location: `src/hr_minds/media/`.

The Media module provides local filesystem resume discovery and cataloging for HR Minds. Instead of manual file-by-file uploads, administrators and hiring managers can register local folders containing candidate resumes. The platform scans and catalogs these resumes, tracks filesystem modifications, and streams live scanning progress via Server-Sent Events (SSE).

Discovered media records (`LocalMedia`) serve as the source of truth for downstream resume parsing and Agentic RAG indexing pipelines.

---

## 🏗️ Architecture & Operating Model

```text
Local Folder (/path/to/resumes)
      │
      ▼
Scanner Engine (_walk)
  • Recursively scans directories
  • Filters by EXTENSION_MAP (.pdf, .docx, .png, etc.)
      │
      ▼
PostgreSQL Database
  • Upserts LocalMedia records (batch size = 500)
  • Prunes deleted files (relative_path NOT IN found)
  • Updates file modification timestamp & scan metadata
      │
      ▼
Server-Sent Events (SSE) Stream
  • event: registered ──> initial scan entity details
  • event: progress   ──> emitted per discovered resume file
  • event: summary    ──> final file & category tallies
```

### 1. Host-Bound Scans
Because file paths are tied to the local machine where the API service runs, each scan record records host identity metadata upon registration:
- **`hostname`**: System network name (e.g., `srijan-mbp`, `HR-WORKSTATION-01`).
- **`os_name`**: Operating system (`macOS`, `Linux`, `Windows`).
- **`os_version`**: Operating system release/version.

**Machine Isolation Rule:**
A registered folder is bound to the `hostname` it was registered on. Re-scanning a folder on a machine with a mismatched hostname is refused with an SSE `error` event:
```json
{
  "event": "error",
  "detail": "Folder is on workstation-01; this system is laptop-02"
}
```

### 2. Dual Scan Lifecycle

The scanner operates in two complementary modes:

1. **Automatic Startup Scan (`scan_all`)**:
   - Executed inside the FastAPI application `lifespan` in `src/hr_minds/main.py`.
   - Queries `LocalMediaScan.list_for_host(db, socket.gethostname())`.
   - Iterates through every folder registered for the current host across all organizations, re-syncing changes and deletions before the API begins receiving HTTP traffic.
   - Sets `last_scanned_by_id = None` (system-initiated).

2. **On-Demand Scan via SSE (`scan_stream`)**:
   - Triggered upon folder registration (`POST /api/v1/media/local-scans`) or manual re-scan (`POST /api/v1/media/local-scans/{scan_id}/scan`).
   - Streams live progress back to the caller over an HTTP connection using `fastapi.sse.EventSourceResponse`.
   - Sets `last_scanned_by_id` to the authenticated user and records `last_scanned_at`.

---

## 📄 Supported Resume Formats

The scanner inspects file extensions case-insensitively and maps them to high-level `MediaType` categories:

| File Extension | `MediaType` | Description |
| :--- | :--- | :--- |
| `.pdf` | `pdf` | Portable Document Format resumes |
| `.doc`, `.docx` | `document` | Microsoft Word documents |
| `.jpg`, `.jpeg`, `.png`, `.webp` | `image` | Scanned image resumes or portfolio pages |

Any directory matching a file name, temporary files, hidden files, or unlisted file extensions (e.g., `.txt`, `.csv`, `.zip`, `.exe`) are automatically ignored. Subdirectories within registered folders are traversed recursively, preserving relative path hierarchies.

---

## 🗄️ Database Schema & Relationships

### `LocalMediaScan`
Represents a registered local folder configuration:

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `Integer` | Primary key |
| `org_id` | `Integer` (FK $\rightarrow$ `organization.id`) | Tenant organization (CASCADE on delete) |
| `created_by_id` | `Integer` (FK $\rightarrow$ `user.id`) | User who registered the folder (CASCADE on delete) |
| `name` | `String(255)` | Human-readable label (e.g., `"Engineering Candidates 2026"`) |
| `folder_path` | `String(1024)` | Absolute path on disk |
| `hostname` | `String(255)` | Machine hostname where the folder resides |
| `os_name` | `String(50)` | OS name when registered or last scanned |
| `os_version` | `String(100)` | OS version when registered or last scanned |
| `last_scanned_by_id` | `Integer` (FK $\rightarrow$ `user.id`, nullable) | User who ran the last manual scan (SET NULL on delete; null for startup scans) |
| `last_scanned_at` | `DateTime(timezone=True)`, nullable | Timestamp of the most recent scan completion |
| `created` / `modified` | `DateTime(timezone=True)` | Audit timestamps |

### `LocalMedia`
Represents a single discovered resume file within a scan folder:

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `Integer` | Primary key |
| `scan_id` | `Integer` (FK $\rightarrow$ `local_media_scan.id`) | Parent scan (CASCADE on delete) |
| `org_id` | `Integer` (FK $\rightarrow$ `organization.id`) | Tenant organization (CASCADE on delete) |
| `relative_path` | `String(1024)` | Path relative to `folder_path` (e.g., `engineering/john_doe.pdf`) |
| `file_name` | `String(255)` | Base filename (e.g., `john_doe.pdf`) |
| `media_type` | `String(20)` | Enum: `pdf`, `document`, or `image` |
| `file_size_bytes` | `BigInteger` | File size in bytes |
| `file_modified_at` | `DateTime(timezone=True)` | Filesystem modification time (`st_mtime`) in UTC |
| `created` / `modified` | `DateTime(timezone=True)` | Audit timestamps |

**Unique Constraint:**
- A compound unique constraint on `(scan_id, relative_path)` ensures idempotent upserts and prevents duplicate file records.

**Filesystem Safety:**
- Deleting a `LocalMediaScan` via the API removes the scan record and all associated `LocalMedia` database rows via `ON DELETE CASCADE`. **Physical files on the host disk are never deleted or modified.**

---

## ⚡ Synchronization & Batch Processing

1. **Batch Upserts (`BATCH_SIZE = 500`)**:
   - Files are discovered asynchronously in a worker thread (`asyncio.to_thread(_walk)`).
   - Rows are upserted into PostgreSQL using `insert(LocalMedia).on_conflict_do_update`.
   - If a file already exists in the scan, its `file_size_bytes` and `file_modified_at` are refreshed in place.

2. **Automatic Pruning**:
   - After upserting found files, the scanner issues a `DELETE FROM local_media WHERE scan_id = :id AND relative_path NOT IN (:found_paths)`.
   - Files deleted from the local disk are automatically purged from the database, and the count is reported in the scan summary event.

3. **Incremental RAG Preparation**:
   - The `file_modified_at` timestamp enables downstream RAG pipelines to compare the file timestamp against the embedding store and only re-index updated resumes.

---

## 📡 Server-Sent Events (SSE) Protocol

Both registration (`POST /media/local-scans`) and manual rescans (`POST /media/local-scans/{scan_id}/scan`) respond with `Content-Type: text/event-stream`.

### Event Types:

#### 1. `event: registered` *(Registration only)*
Emitted as soon as the folder registration is committed to the database before the scan starts:
```text
event: registered
data: {"id":1,"name":"Resumes","folder_path":"/Users/shree/resumes","hostname":"srijan-mbp","os_name":"macOS","os_version":"15.1","created_by_email":"alice@example.com","last_scanned_by_email":null,"last_scanned_at":null,"created":"2026-11-14T10:00:00Z","modified":"2026-11-14T10:00:00Z"}
```

#### 2. `event: progress`
Emitted for every valid resume discovered during the walk:
```text
event: progress
data: {"file":"engineering/alice_cv.pdf","media_type":"pdf","count":1}
```

#### 3. `event: summary`
Emitted upon scan completion with comprehensive counters:
```text
event: summary
data: {"total":142,"removed":3,"pdf":110,"document":25,"image":7,"hostname":"srijan-mbp","os_name":"macOS","os_version":"15.1","scanned_by_email":"alice@example.com"}
```

#### 4. `event: error`
Emitted if the directory does not exist on disk or if the hostname does not match:
```text
event: error
data: {"detail":"Folder is on srijan-mbp; this system is backup-node"}
```

---

## 🔐 RBAC & Permissions

The media module integrates with HR Minds' Role-Based Access Control and multi-tenant organization scoping:

| Endpoint | Required Permission | Description |
| :--- | :--- | :--- |
| `POST /api/v1/media/local-scans` | `media:create` | Register a new local folder and start initial scan |
| `GET /api/v1/media/local-scans` | `media:read` | List all registered local folders for the organization |
| `GET /api/v1/media/local-scans/{id}/files` | `media:read` | List all discovered resumes inside a registered folder |
| `POST /api/v1/media/local-scans/{id}/scan` | `media:create` | Trigger an on-demand re-scan of a registered folder |
| `DELETE /api/v1/media/local-scans/{id}` | `media:delete` | Unregister a folder and remove its file catalog |

### Pre-Stream HTTP Validation
To preserve clean HTTP API semantics for client applications, validation occurs before opening the SSE stream:
- Registering a non-existent or invalid directory path returns an immediate `422 Unprocessable Content` (`{"detail": "Folder path does not exist or is not a directory"}`).
- Requesting an unknown scan ID or a scan belonging to another organization returns an immediate `404 Not Found` (`{"detail": "Local media scan not found"}`).
