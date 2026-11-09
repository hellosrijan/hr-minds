# API Reference

Every endpoint of the HR Minds API, with request and response examples. The examples are real responses captured from the running app.

Interactive docs, generated from the code, are served at `/docs` (Swagger UI) and `/redoc`.

**Contents:** [Conventions](#conventions) · [Auth](#auth) · [Features](#features) · [Organizations](#organizations) · [Roles](#roles) · [Members](#members) · [Invitations](#invitations) · [Walkthrough](#walkthrough-curl)

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

### Permissions

Each organization endpoint requires a `feature:action` permission, e.g. `roles:create`, listed under **Requires** below. The organization **owner** has every permission. Other members have the permissions of their single role.

| Feature | Covers |
| :--- | :--- |
| `members` | Viewing members, inviting, changing roles, removing |
| `roles` | Viewing and editing custom roles |

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

---

## Features

### `GET /features`

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

## Organizations

### `GET /orgs`

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

## Roles

All role endpoints act on the organization in [`X-Org-Id`](#choosing-the-organization-x-org-id), or on your own organization if it's omitted.

A role's permissions are written and returned grouped by feature:

```json
"permissions": [
  { "feature": "members", "actions": ["create", "read"] },
  { "feature": "roles", "actions": ["read"] }
]
```

### `GET /roles`

**Requires:** `roles:read`. **Response** `200 OK`: a list of [roles](#post-roles), sorted by name.

### `POST /roles`

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

### `GET /roles/{role_id}`

**Requires:** `roles:read`. **Response** `200 OK`: one role. **Errors:** `404 Role not found`, which also covers roles from other organizations.

### `PATCH /roles/{role_id}`

Change any of `name`, `description`, `permissions`. Omitted fields stay as they are. `permissions`, when sent, **replaces** the whole set.

**Requires:** `roles:update`. You must also already hold every permission the role currently grants, and every permission you set.

```json
{ "description": "Invites and manages team members" }
```

**Response** `200 OK`: the updated role. **Errors:** as for [create](#post-roles), plus `404 Role not found`.

### `DELETE /roles/{role_id}`

**Requires:** `roles:delete`, plus every permission the role grants. **Response:** `204 No Content`. Pending invitations for the role are deleted with it.

**Errors:** `404 Role not found` · `409 Role is assigned to members; reassign them first`

---

## Members

All member endpoints act on the organization in [`X-Org-Id`](#choosing-the-organization-x-org-id), or on your own organization if it's omitted.

### `GET /members`

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

### `PATCH /members/{user_id}`

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

### `DELETE /members/{user_id}`

Remove a member from the organization. Their account and other memberships are untouched.

**Requires:** `members:delete`, plus every permission of their role. **Response:** `204 No Content`. **Errors:** same `403` and `404` responses as [PATCH](#patch-membersuser_id).

---

## Invitations

Inviting works the same for existing and new users: the invitee logs in (signing up first if needed) and accepts. No email is sent yet, so share the `accept_url` yourself.

### `POST /invitations`

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

### `POST /invitations/{token}/accept`

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
  -d '{"name":"HR Manager","permissions":[{"feature":"members","actions":["read","create"]}]}' | jq -r .id)

# 4. Alice invites Bob and shares the link
URL=$(curl -s -X POST $API/invitations -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' \
  -d "{\"email\":\"bob@example.com\",\"role_id\":$ROLE}" | jq -r .accept_url)

# 5. Bob accepts and gets Alice's organization id
ORG=$(curl -s -X POST "$URL" -H "Authorization: Bearer $BOB" | jq -r .id)

# 6. Bob works in Alice's organization
curl -s $API/members -H "Authorization: Bearer $BOB" -H "X-Org-Id: $ORG"
```
