# Authentication & RBAC

Code: `src/hr_minds/auth/`.

## Passwords

`User` hashes passwords with Argon2id (`pwdlib.PasswordHash.recommended()`). Only the hash is stored. `services.authenticate_user` verifies against a dummy hash when the email is unknown so login timing does not reveal which emails exist, and checks `is_active` only after the password matches.

## Sessions (JWT + database row)

Each login inserts an `AccessToken` row and returns a signed JWT with `sub` (user id), `exp` and `jti`.

A request is authenticated only if **both** hold (`dependencies.get_token_payload`):

1. The JWT signature and expiry are valid (`SECRET_KEY`, `ALGORITHM`).
2. An `access_token` row with that `jti` exists, is not revoked and has not expired.

`POST /auth/logout` sets `revoked_at` on the row, so the token stops working immediately. Expired rows are deleted by `uv run python -m hr_minds.auth.tasks`.

`get_current_user` then loads the user and rejects inactive or deleted accounts with 401.

## Organizations & RBAC

RBAC is per organization (multi-tenant). Code: `models/org.py`, `models/rbac.py`, `services/rbac.py`, `router/rbac.py`.

- **Signup** (`POST /auth/register`, public) creates the user, a personal `organization` they own (named after their first name), and an owner `membership`.
- **Organization IDs** shown to clients are `public_id`s like `org_srijan_k3x9p2m7qa`: `org_`, the name lowercased with other characters turned into `-` (max 30), and 10 random characters. Set once at creation; the integer `id` stays internal.
- **Features and permissions** come from code: `FEATURES` × `DEFAULT_ACTIONS` in `settings/features.py`, written to `feature`/`permission` by `uv run python -m hr_minds.auth.cli sync-features`. Rerun it after adding a feature.
- **Roles** belong to one org and have a custom name (unique per org). The owner picks which `feature:action` pairs each role grants.
- **Membership** links a user to an org with **one** role. The owner's membership has no role; owners can do everything in their org.
- **Invitations** add anyone, existing account or not. The invitee logs in with the invited email and calls the `accept_url`. Only a SHA-256 of the token is stored; links are single-use and expire after 7 days. No email is sent yet: the inviter shares the link.

Tables: `organization` ← `membership` → `user`; `membership` → `role` → `role_permission` → `permission` → `feature`; `invitation` → `organization`, `role`.

### Protecting an endpoint

Clients pick the organization with the `X-Org-Id` header (a public id). Without it, the user's **own** organization is used, so single-org users never need it. `require(feature, action)` resolves the header and returns the caller's `Membership`:

```python
from hr_minds.auth.dependencies import require
from hr_minds.settings.features import FeatureSlug

@router.get("/media")
async def list_media(membership: Membership = Depends(require(FeatureSlug.MEDIA, "read")), db=...):
    return await db.scalars(select(Media).where(Media.org_id == membership.org_id))
```

Never read the org from the request yourself; use `membership.org_id`, which `require()` has already verified.

Non-members get **404** (so outsiders can't tell the org exists); members without the permission get **403**. `is_superuser` does **not** bypass org checks: tenant data stays inside its org.

Any table holding org data (media, recruitment, …) needs an `org_id` column, and every query must filter by `membership.org_id`.

### Escalation rules (`services/rbac.py`)

A non-owner can only grant, edit, delete or assign roles whose permissions they hold themselves, and can only manage members whose current role they could have granted. Nobody can change the owner's membership or their own. Violations return 403.

Tests for isolation, invitations and escalation: `tests/test_rbac.py`.

## Errors

| Situation | Status |
| :--- | :--- |
| Missing / invalid / revoked token | 401 (`WWW-Authenticate: Bearer`) |
| Wrong email or password | 401 `Incorrect email or password` |
| Correct password, disabled account | 403 `Account is disabled` |
| Not a member of the org | 404 `Organization not found` |
| Missing permission | 403 `Access denied` |
| Granting/managing beyond your permissions, or changing owner/self | 403 |
| Unknown role, member, or invalid/expired/used invitation | 404 |
| Email already registered, duplicate role name, role still assigned, already a member | 409 |
| Unknown feature or action | 422 |
