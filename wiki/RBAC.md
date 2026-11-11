# RBAC (Role-Based Access Control)

The Role-Based Access Control (RBAC) feature in HR Minds is fully **organization-scoped** (multi-tenant). Every user belongs to one or more organizations, and permissions are granted through custom roles created within each organization.

---

## 👥 Architecture & Tenant Model

### 1. Personal Organization on Signup
- When a user registers via `POST /api/v1/auth/register`, a personal **`Organization`** is automatically created and assigned to them as the **Owner**.
- Every user always belongs to at least one organization by default.

### 2. Organization Public IDs (`X-Org-Id`)
- Organizations are identified externally by a secure, immutable `public_id` string:
  ```text
  org_<slug>_<10 random chars>
  Example: org_alice_k3x9p2m7qa
  ```
- Clients target an organization by passing the `X-Org-Id` HTTP header:
  ```http
  X-Org-Id: org_alice_k3x9p2m7qa
  ```
- **Default fallback**: If `X-Org-Id` is omitted, the API automatically operates on the user's **personal organization** (the one they own).

### 3. Role & Membership Model
- **Owner**:
  - The organization owner bypasses permission checks and has full access across all features.
  - The owner's `Membership` record has `is_owner=True` and `role=None`.
  - An owner cannot have their role changed or be removed from their own organization.
- **Members**:
  - Each non-owner member holds exactly **one** role in that organization (`Membership.role_id`).
  - Roles are **organization-scoped**: Role definitions created in Org A do not exist or bleed into Org B.
- **Invitations**:
  - Existing members with `members:create` can invite anyone via email.
  - Invitations store a SHA-256 hash of a secure token, expire in 7 days, and are single-use.
  - The invitee must log in using the exact invited email address to accept the invitation.

---

## 🛡️ Security & Escalation Guards

To prevent privilege escalation, non-owner members are subject to strict authorization guards:

1. **Permission Subsetting**:
   - A member cannot create or update a role with permissions they do not currently hold.
   - A member cannot invite another user into a role with permissions they do not currently hold.
2. **Immutable Protected Targets**:
   - Members cannot alter the role of the organization owner.
   - Members cannot alter or remove their own role.
3. **Strict Tenant Isolation**:
   - Any query attempting to access or modify resources in an organization the caller does not belong to returns `404 Organization not found` (deliberately masking whether the organization exists to prevent enumeration).
   - `is_superuser` does **not** bypass organization scoping; tenant boundaries remain strictly isolated.

---

## 💻 Developer Guide: Protecting an Endpoint

To secure an endpoint with RBAC, inject the `require(feature, action)` dependency:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.dependencies import require
from hr_minds.auth.models import Membership
from hr_minds.settings.db import get_db
from hr_minds.settings.features import FeatureSlug

router = APIRouter(prefix="/media", tags=["Media"])

@router.get("", summary="List Organization Media")
async def list_media(
    membership: Membership = Depends(require(FeatureSlug.MEDIA, "read")),
    db: AsyncSession = Depends(get_db),
):
    # Always scope queries by membership.org_id
    query = select(Media).where(Media.org_id == membership.org_id)
    return (await db.scalars(query)).all()
```

---

## 🌐 RBAC Endpoints Quick Reference

All endpoints below are prefixed with `/api/v1` and require an `Authorization: Bearer <access_token>` header. For complete request and response payloads, see the [API Reference](API-Endpoints).

| Method | Endpoint | Required Permission | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/features` | Any authenticated user | List global features and available actions |
| `GET` | `/orgs` | Any authenticated user | List organizations the user belongs to and their role |
| `GET` | `/roles` | `roles:read` | List all roles in the organization |
| `POST` | `/roles` | `roles:create` + escalation check | Create a new custom role with permissions |
| `GET` | `/roles/{role_id}` | `roles:read` | Retrieve details for a specific role |
| `PATCH` | `/roles/{role_id}` | `roles:update` + escalation check | Update role name, description, or permissions |
| `DELETE` | `/roles/{role_id}` | `roles:delete` + escalation check | Delete a role (fails if still assigned to members) |
| `GET` | `/members` | `members:read` | List members and their assigned roles |
| `PATCH` | `/members/{user_id}` | `members:update` + escalation check | Change a member's role |
| `DELETE` | `/members/{user_id}` | `members:delete` + escalation check | Remove a member from the organization |
| `POST` | `/invitations` | `members:create` + escalation check | Invite a user by email to join with a role |
| `POST` | `/invitations/{token}/accept` | Authenticated (invited email) | Accept invitation and join organization |

---

## ⚠️ Common RBAC Error Responses

| Status Code | Error Message / `detail` | Cause |
| :--- | :--- | :--- |
| `401 Unauthorized` | `Invalid or expired token` | Missing, expired, or revoked JWT |
| `403 Forbidden` | `Access denied` | Caller lacks the required `feature:action` permission |
| `403 Forbidden` | `You can't grant or manage permissions you don't have` | Privilege escalation violation |
| `403 Forbidden` | `The owner and your own membership can't be changed` | Attempted modification of owner or self |
| `404 Not Found` | `Organization not found` | Invalid `X-Org-Id` or caller is not a member |
| `404 Not Found` | `Role not found` / `Member not found` | Targeted entity does not exist in this organization |
| `404 Not Found` | `Invitation not found or expired` | Invalid, expired, or already used invite token |
| `409 Conflict` | `A role with this name already exists` | Duplicate role name within the organization |
| `409 Conflict` | `Role is assigned to members; reassign them first` | Deletion blocked while role has active members |
| `409 Conflict` | `User is already a member of this organization` | Inviting an existing member |
| `422 Unprocessable` | `Unknown feature or action` | Invalid permission payload |
