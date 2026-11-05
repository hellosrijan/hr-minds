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

## RBAC

Tables: `feature` → `permission` (feature + action, unique) ← `role_permission` → `role` ← `user_role` → `user`.

Protect an endpoint with `require(feature, action)`:

```python
from hr_minds.auth.dependencies import require
from hr_minds.settings.features import FeatureSlug

@router.post("/upload", dependencies=[Depends(require(FeatureSlug.MEDIA, "create"))])
async def upload(...): ...
```

Superusers pass every check. Everyone else needs a role granting that `feature:action`; otherwise 403 `Access denied`.

## Errors

| Situation | Status |
| :--- | :--- |
| Missing / invalid / revoked token | 401 (`WWW-Authenticate: Bearer`) |
| Wrong email or password | 401 `Incorrect email or password` |
| Correct password, disabled account | 403 `Account is disabled` |
| Missing permission | 403 `Access denied` |
| Email already registered | 409 |
