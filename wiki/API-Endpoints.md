# API Reference

Every endpoint of the HR Minds API, with request and response examples. The examples are real responses captured from the running app.

Interactive docs, generated from the code, are served at `/docs` (Swagger UI) and `/redoc`.

**Contents:** [Conventions](#conventions) · [Auth](#auth) · [RBAC](#rbac) ([Features](#features) · [Organizations](#organizations) · [Roles](#roles) · [Members](#members) · [Invitations](#invitations)) · [Media](#media) ([Local Scans](#local-media-scans)) · [Walkthrough](#walkthrough-curl)

---

## Conventions

### Base URL

All routes are under `/api/v1`, e.g. `http://127.0.0.1:8000/api/v1`.

### Authentication

Log in with [`POST /auth/token`](#post-authtoken) and send the token on every other request:

```http
Authorization: Bearer <access_token>
```

Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30) or when you [log out](#post-authlogout).

### Choosing the organization: `X-Org-Id`

Endpoints that act on an organization ([Roles](#roles), [Members](#members), [Invitations](#invitations)) read the organization from the `X-Org-Id` header:

```http
X-Org-Id: org_alice_gqbwyaynhh
```

- **Omitted:** the request uses the organization **you own** (every user gets one at signup). Single-organization users never need the header.
- **Set:** use the `id` of any organization from [`GET /orgs`](#get-orgs).
- **Not a member of that organization:** `404 Organization not found`.

Organization IDs look like `org_<name>_<10 random characters>`. They never change, even if the organization is renamed.

### Pagination

List endpoints that can return many rows are paginated and return an envelope instead of a bare array. Currently this is `GET /media/local-scans/{scan_id}/files`.

| Query parameter | Default | Limits |
| :--- | :--- | :--- |
| `page` | `1` | `>= 1` (1-based) |
| `page_size` | `20` | `1` to `100` |

```json
{
  "items": [ /* the files on this page */ ],
  "total": 5,
  "page": 2,
  "page_size": 2,
  "total_pages": 3
}
```

- `total` counts every matching row, not just this page. `total_pages` is `ceil(total / page_size)`, or `0` when there are no rows.
- A page past the end is not an error: `200 OK` with empty `items` and the real `total` and `total_pages`.
- `page < 1`, `page_size < 1` or `page_size > 100` returns `422 Validation Error`.
- Rows come back in a fixed order (files are sorted by `relative_path`), so pages never overlap.

### Permissions

Each organization endpoint requires a `feature:action` permission, e.g. `roles:create`, listed under **Requires** below. The organization **owner** has every permission. Other members have the permissions of their single role.

| Feature | Covers |
| :--- | :--- |
| `members` | Viewing members, inviting, changing roles, removing |
| `roles` | Viewing and editing custom roles |
| `media` | Registering local resume folders, triggering scans, listing discovered files, deleting scans |

Actions are always `create`, `read`, `update`, `delete`. [`GET /features`](#get-features) lists what is currently available.

**Escalation rule:** members can only grant, edit, delete or assign roles whose permissions they hold themselves, and can't change the owner's membership or their own. Breaking it returns `403`.

### Errors

Errors return JSON with a `detail` field:

```json
{ "detail": "Role not found" }
```

Request-body validation errors (`422`) return FastAPI's list format:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      "input": "short",
      "ctx": { "min_length": 8 }
    }
  ]
}
```

| Status | Meaning |
| :--- | :--- |
| `401` | Missing, invalid, expired or revoked token |
| `403` | Logged in but not allowed: missing permission, escalation, or protected member |
| `404` | Not found, including organizations you don't belong to |
| `409` | Conflicts with existing data |
| `422` | Invalid request body or unknown feature/action |

---

## Auth

### `POST /auth/register`

Public sign-up. Creates the user **and** a personal organization they own, named after their first name.

**Body** (JSON)

| Field | Type | Rules |
| :--- | :--- | :--- |
| `email` | string | Valid email, unique (case-insensitive) |
| `first_name` | string | 1–100 characters |
| `last_name` | string | 1–100 characters |
| `password` | string | 8–128 characters |

```json
{
  "email": "alice@example.com",
  "first_name": "Alice",
  "last_name": "Smith",
  "password": "password123"
}
```

**Response** `201 Created`: the user. Passwords and admin flags are never returned.

```json
{
  "id": 1,
  "email": "alice@example.com",
  "first_name": "Alice",
  "last_name": "Smith",
  "created": "2026-11-09T17:57:09.953770Z",
  "modified": "2026-11-09T17:57:09.953770Z"
}
```

**Errors:** `409 Email already registered` · `422` invalid body

### `POST /auth/token`

Log in. Uses the OAuth2 password form, so it's sent as **form data**, not JSON. Swagger's **Authorize** button uses this endpoint.

**Body** (`application/x-www-form-urlencoded`)

| Field | Value |
| :--- | :--- |
| `username` | The user's email (case-insensitive) |
| `password` | The password |

**Response** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors**

| Status | `detail` | When |
| :--- | :--- | :--- |
| `401` | `Incorrect email or password` | Wrong password **or** unknown email (deliberately the same) |
| `403` | `Account is disabled` | Correct password, but the account is inactive |

### `POST /auth/logout`

Revokes the token used for this request. Other sessions of the same user keep working.

**Requires:** Bearer token. **Response:** `204 No Content`. Afterwards the token gets `401 Session is revoked or expired`.

### `GET /auth/me`

The logged-in user.

**Requires:** Bearer token. **Response** `200 OK`: same shape as [register](#post-authregister).

**Errors:** `401 Not authenticated` (no token) · `401 Invalid or expired token` · `401 Session is revoked or expired` · `401 User is inactive or no longer exists`

### `DELETE /auth/me`

Permanently delete your account. Confirm with your password in the body.

**Requires:** Bearer token.

```json
{ "password": "password123" }
```

**Response:** `204 No Content`. What happens to related data:

| Data | Result |
| :--- | :--- |
| Your memberships in other organizations | Removed. Those organizations, their roles and other members are untouched |
| Your own organization | Deleted, with its roles and pending invitations |
| Invitations you sent to other organizations | Stay valid |
| Your sessions | Deleted; all your tokens stop working |

The email can be registered again afterwards.

**Errors**

| Status | `detail` | When |
| :--- | :--- | :--- |
| `403` | `Incorrect password` | Wrong password |
| `409` | `Your organization still has members; remove them before deleting your account` | Others are still in your own organization; [remove them](#delete-membersuser_id) first |

---

## RBAC

Endpoints for managing the Role-Based Access Control system, tenant organizations, custom roles, memberships, and team invitations. All RBAC endpoints require `Authorization: Bearer <access_token>` and act on the organization specified by `X-Org-Id` (or the caller's personal organization by default).

### Features

#### `GET /features`

Features and the actions that can be granted on each. Use it to build a role editor.

**Requires:** Bearer token. **Response** `200 OK`

```json
[
  {
    "slug": "members",
    "name": "Members",
    "description": "Invite members and manage their roles",
    "actions": ["create", "read", "update", "delete"]
  },
  {
    "slug": "roles",
    "name": "Roles",
    "description": "Custom roles and their permissions",
    "actions": ["create", "read", "update", "delete"]
  }
]
```

---

### Organizations

#### `GET /orgs`

Organizations you belong to, with your role in each. Use it for an organization switcher; send the chosen `id` as `X-Org-Id`.

**Requires:** Bearer token. **Response** `200 OK`

```json
[
  {
    "id": "org_bob_q801nqdfn9",
    "name": "Bob",
    "is_owner": true,
    "role": null
  },
  {
    "id": "org_alice_gqbwyaynhh",
    "name": "Alice",
    "is_owner": false,
    "role": { "id": 1, "name": "HR Manager" }
  }
]
```

`role` is `null` for the owner, who has every permission.

---

### Roles

All role endpoints act on the organization in [`X-Org-Id`](#choosing-the-organization-x-org-id), or on your own organization if it's omitted.

A role's permissions are written and returned grouped by feature:

```json
"permissions": [
  { "feature": "members", "actions": ["create", "read"] },
  { "feature": "roles", "actions": ["read"] }
]
```

#### `GET /roles`

**Requires:** `roles:read`. **Response** `200 OK`: a list of [roles](#post-roles), sorted by name.

#### `POST /roles`

Create a custom role.

**Requires:** `roles:create`, plus every permission you grant (see the escalation rule).

**Body**

| Field | Type | Rules |
| :--- | :--- | :--- |
| `name` | string | 1–100 characters, unique within the organization |
| `description` | string \| null | Up to 255 characters. Optional |
| `permissions` | list | `[{ "feature": ..., "actions": [...] }]`. Optional, defaults to none |

```json
{
  "name": "HR Manager",
  "description": "Manages the team",
  "permissions": [
    { "feature": "members", "actions": ["read", "create"] },
    { "feature": "roles", "actions": ["read"] }
  ]
}
```

**Response** `201 Created`

```json
{
  "id": 1,
  "name": "HR Manager",
  "description": "Manages the team",
  "permissions": [
    { "feature": "members", "actions": ["create", "read"] },
    { "feature": "roles", "actions": ["read"] }
  ]
}
```

**Errors**

| Status | `detail` | When |
| :--- | :--- | :--- |
| `403` | `Access denied` | You lack `roles:create` |
| `403` | `You can't grant or manage permissions you don't have` | The role grants something you don't hold |
| `409` | `A role with this name already exists` | Duplicate name in this organization |
| `422` | `Unknown feature or action` | e.g. `"actions": ["fly"]`, or a feature not yet enabled |
| `422` | validation list | `feature` isn't a known slug |

#### `GET /roles/{role_id}`

**Requires:** `roles:read`. **Response** `200 OK`: one role. **Errors:** `404 Role not found`, which also covers roles from other organizations.

#### `PATCH /roles/{role_id}`

Change any of `name`, `description`, `permissions`. Omitted fields stay as they are. `permissions`, when sent, **replaces** the whole set.

**Requires:** `roles:update`. You must also already hold every permission the role currently grants, and every permission you set.

```json
{ "description": "Invites and manages team members" }
```

**Response** `200 OK`: the updated role. **Errors:** as for [create](#post-roles), plus `404 Role not found`.

#### `DELETE /roles/{role_id}`

**Requires:** `roles:delete`, plus every permission the role grants. **Response:** `204 No Content`. Pending invitations for the role are deleted with it.

**Errors:** `404 Role not found` · `409 Role is assigned to members; reassign them first`

---

### Members

All member endpoints act on the organization in [`X-Org-Id`](#choosing-the-organization-x-org-id), or on your own organization if it's omitted.

#### `GET /members`

**Requires:** `members:read`. **Response** `200 OK`, in order of joining:

```json
[
  {
    "user": {
      "id": 1,
      "email": "alice@example.com",
      "first_name": "Alice",
      "last_name": "Smith",
      "created": "2026-11-09T17:58:05.821529Z",
      "modified": "2026-11-09T17:58:05.821529Z"
    },
    "role": null,
    "is_owner": true,
    "created": "2026-11-09T17:58:05.821529Z"
  },
  {
    "user": {
      "id": 2,
      "email": "bob@example.com",
      "first_name": "Bob",
      "last_name": "Jones",
      "created": "2026-11-09T17:58:05.884126Z",
      "modified": "2026-11-09T17:58:05.884126Z"
    },
    "role": { "id": 1, "name": "HR Manager" },
    "is_owner": false,
    "created": "2026-11-09T17:58:06.238150Z"
  }
]
```

`created` on a member is when they joined the organization.

#### `PATCH /members/{user_id}`

Give a member a different role. `user_id` is the user's `id`.

**Requires:** `members:update`. You must also hold every permission of the member's current role and of the new role.

```json
{ "role_id": 3 }
```

**Response** `200 OK`: the updated member, same shape as in the list.

**Errors**

| Status | `detail` | When |
| :--- | :--- | :--- |
| `403` | `The owner and your own membership can't be changed` | Target is the owner or yourself |
| `403` | `You can't grant or manage permissions you don't have` | Escalation |
| `404` | `Member not found` / `Role not found` | |

#### `DELETE /members/{user_id}`

Remove a member from the organization. Their account and other memberships are untouched.

**Requires:** `members:delete`, plus every permission of their role. **Response:** `204 No Content`. **Errors:** same `403` and `404` responses as [PATCH](#patch-membersuser_id).

---

### Invitations

Inviting works the same for existing and new users: the invitee logs in (signing up first if needed) and accepts. No email is sent yet, so share the `accept_url` yourself.

#### `POST /invitations`

Invite someone into the organization in [`X-Org-Id`](#choosing-the-organization-x-org-id) with a role.

**Requires:** `members:create`, plus every permission of the role.

```json
{ "email": "bob@example.com", "role_id": 1 }
```

**Response** `201 Created`

```json
{
  "id": 1,
  "email": "bob@example.com",
  "role": { "id": 1, "name": "HR Manager" },
  "expires_at": "2026-11-16T17:58:06.209211Z",
  "accept_url": "http://127.0.0.1:8000/api/v1/invitations/7kMcR-ci0tVVfPLVPm1WQtVie53_TBgRCiQFBkCAnZg/accept"
}
```

The `accept_url` is shown **only in this response**; only a hash of it is stored. It works once and expires after 7 days.

**Errors:** `403` escalation · `404 Role not found` · `409 User is already a member of this organization`

#### `POST /invitations/{token}/accept`

Join the organization. You must be logged in with the **invited email**.

**Requires:** Bearer token. **Response** `200 OK`: the organization you joined, as in [`GET /orgs`](#get-orgs).

```json
{
  "id": "org_alice_gqbwyaynhh",
  "name": "Alice",
  "is_owner": false,
  "role": { "id": 1, "name": "HR Manager" }
}
```

**Errors:** `404 Invitation not found or expired` (unknown, used, expired, or for a different email) · `409 User is already a member of this organization`

---

## Media

Endpoints for registering and scanning local candidate resume folders (`pdf`, `doc`, `docx`, `jpg`, `jpeg`, `png`, `webp`). All media endpoints require `Authorization: Bearer <access_token>` and act on the organization specified by `X-Org-Id` (or the caller's personal organization by default).

Streaming endpoints use **Server-Sent Events (SSE)**. In cURL, pass `-N` (unbuffered) to observe events in real time.

### Local Media Scans

#### `POST /media/local-scans`

Register a local folder path and immediately start the initial scan, streaming live progress back over SSE.

**Requires:** `media:create`.

**Pre-stream validation:** If `folder_path` does not exist or is not a directory, the endpoint returns `422 Unprocessable Content` before opening the stream.

**Body** (JSON)

| Field | Type | Rules |
| :--- | :--- | :--- |
| `name` | string | 1–255 characters |
| `folder_path` | string | 1–1024 characters, must resolve to an existing local directory |

```json
{
  "name": "Engineering Resumes",
  "folder_path": "/Users/alice/Documents/resumes"
}
```

**Response** `201 Created` (`Content-Type: text/event-stream`)

```text
event: registered
data: {"id":1,"name":"Engineering Resumes","folder_path":"/Users/alice/Documents/resumes","hostname":"alice-macbook","os_name":"macOS","os_version":"15.1","created_by_email":"alice@example.com","last_scanned_by_email":null,"last_scanned_at":null,"created":"2026-11-14T10:15:28Z","modified":"2026-11-14T10:15:28Z"}

event: progress
data: {"file":"alice_cv.pdf","media_type":"pdf","count":1}

event: progress
data: {"file":"subfolder/bob_resume.docx","media_type":"document","count":2}

event: summary
data: {"total":2,"removed":0,"pdf":1,"document":1,"image":0,"hostname":"alice-macbook","os_name":"macOS","os_version":"15.1","scanned_by_email":"alice@example.com"}
```

**Errors**
| Status | `detail` | When |
| :--- | :--- | :--- |
| `401` | `Invalid or expired token` | Missing or invalid auth token |
| `403` | `Access denied` | Caller lacks `media:create` permission |
| `422` | `Folder path does not exist or is not a directory` | Path is not a valid directory on the server |

---

#### `GET /media/local-scans`

List all registered local folders for the active organization.

**Requires:** `media:read`. **Response** `200 OK`

```json
[
  {
    "id": 1,
    "name": "Engineering Resumes",
    "folder_path": "/Users/alice/Documents/resumes",
    "hostname": "alice-macbook",
    "os_name": "macOS",
    "os_version": "15.1",
    "created_by_email": "alice@example.com",
    "last_scanned_by_email": "alice@example.com",
    "last_scanned_at": "2026-11-14T10:15:30Z",
    "created": "2026-11-14T10:15:28Z",
    "modified": "2026-11-14T10:15:30Z"
  }
]
```

---

#### `GET /media/local-scans/{scan_id}/files`

List candidate resume files discovered inside a registered folder with pagination.

**Requires:** `media:read`.

**Query Parameters:**
- `page` (optional integer, $\ge 1$, default: `1`): Current page number.
- `page_size` (optional integer, $1 \dots 100$, default: `20`): Number of files per page.

**Response** `200 OK`

```json
{
  "items": [
    {
      "id": 1,
      "scan_id": 1,
      "file_name": "alice_cv.pdf",
      "relative_path": "alice_cv.pdf",
      "file_path": "/Users/hr/resumes/alice_cv.pdf",
      "media_type": "pdf",
      "file_size_bytes": 1048576,
      "file_modified_at": "2026-11-14T09:30:00Z",
      "created": "2026-11-14T10:15:29Z"
    },
    {
      "id": 2,
      "scan_id": 1,
      "file_name": "bob_resume.docx",
      "relative_path": "subfolder/bob_resume.docx",
      "file_path": "/Users/hr/resumes/subfolder/bob_resume.docx",
      "media_type": "document",
      "file_size_bytes": 524288,
      "file_modified_at": "2026-11-14T09:40:00Z",
      "created": "2026-11-14T10:15:29Z"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

**Errors:** `404 Local media scan not found`, `422 Validation Error` (if `page < 1` or `page_size > 100`).

---

#### `POST /media/local-scans/{scan_id}/scan`

Trigger an on-demand re-scan of a registered folder. Detects new and modified files, drops deleted files, and streams progress over SSE.

**Requires:** `media:create`.

**Pre-stream validation:** If `scan_id` does not exist in the active organization, returns `404 Not Found` before opening the stream.

**Response** `200 OK` (`Content-Type: text/event-stream`)

```text
event: progress
data: {"file":"alice_cv.pdf","media_type":"pdf","count":1}

event: summary
data: {"total":1,"removed":1,"pdf":1,"document":0,"image":0,"hostname":"alice-macbook","os_name":"macOS","os_version":"15.1","scanned_by_email":"alice@example.com"}
```

If the endpoint is executed from a machine with a different hostname than the one the folder was registered on, an `error` event is emitted:
```text
event: error
data: {"detail":"Folder is on alice-macbook; this system is worker-node-2"}
```

**Errors:** `404 Local media scan not found`

---

#### `DELETE /media/local-scans/{scan_id}`

Remove a registered folder and delete all its discovered file records from the database. Files on the local disk are untouched.

**Requires:** `media:delete`. **Response:** `204 No Content`.

**Errors:** `404 Local media scan not found`

---

## Walkthrough (curl)

Alice invites Bob into her organization as an HR Manager.

```bash
API=http://127.0.0.1:8000/api/v1

# 1. Both sign up
curl -s -X POST $API/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","first_name":"Alice","last_name":"Smith","password":"password123"}'
curl -s -X POST $API/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"bob@example.com","first_name":"Bob","last_name":"Jones","password":"password123"}'

# 2. Log in
ALICE=$(curl -s -X POST $API/auth/token -d 'username=alice@example.com&password=password123' | jq -r .access_token)
BOB=$(curl -s -X POST $API/auth/token -d 'username=bob@example.com&password=password123' | jq -r .access_token)

# 3. Alice creates a role (no X-Org-Id: her own organization)
ROLE=$(curl -s -X POST $API/roles -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' \
  -d '{"name":"HR Manager","permissions":[{"feature":"members","actions":["read","create"]},{"feature":"media","actions":["create","read","delete"]}]}' | jq -r .id)

# 4. Alice invites Bob and shares the link
URL=$(curl -s -X POST $API/invitations -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' \
  -d "{\"email\":\"bob@example.com\",\"role_id\":$ROLE}" | jq -r .accept_url)

# 5. Bob accepts and gets Alice's organization id
ORG=$(curl -s -X POST "$URL" -H "Authorization: Bearer $BOB" | jq -r .id)

# 6. Bob works in Alice's organization
curl -s $API/members -H "Authorization: Bearer $BOB" -H "X-Org-Id: $ORG"

# 7. Bob registers a local resume folder and streams scan events in real-time
curl -N -s -X POST $API/media/local-scans \
  -H "Authorization: Bearer $BOB" \
  -H "X-Org-Id: $ORG" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Engineering Resumes","folder_path":"/tmp/resumes"}'
```
