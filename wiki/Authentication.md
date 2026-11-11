# Authentication & Session Management

Code location: `src/hr_minds/auth/`.

HR Minds uses an industry-standard security model combining **Argon2id password hashing**, **cryptographically signed JWTs**, and **stateful database-backed token tracking** for immediate revocation.

---

## 🔒 Password Security & Verification

- **Argon2id Hashing**: Passwords are hashed using Argon2id via `pwdlib` (`pwdlib.PasswordHash.recommended()`). Plaintext passwords are never stored or logged.
- **Timing-Safe Verification**: When `authenticate_user` receives an unknown email, it verifies against a static dummy hash. This ensures constant-time execution and prevents account enumeration via response-timing discrepancies.
- **Account State Verification**: The user's `is_active` status is checked strictly after verifying the password hash, preventing attackers from probing for inactive accounts without valid credentials.

---

## 🎟️ Session Lifecycle (JWT + Database Tracking)

Sessions combine stateless JWT verification with stateful database revocation:

1. **Token Issuance (`POST /api/v1/auth/token`)**:
   - Accepts OAuth2-compatible form data (`username` / `password`).
   - Inserts an `access_token` record containing a unique UUID `jti`, the user ID, and an expiry timestamp (`expires_at`).
   - Issues a signed JWT containing claims: `sub` (user ID), `jti` (session UUID), and `exp` (UTC timestamp).
2. **Session Verification (`dependencies.get_token_payload`)**:
   - Every protected request verifies **both**:
     - The JWT cryptographic signature and expiration time (`SECRET_KEY`, `ALGORITHM`).
     - The database `access_token` record with that `jti` exists, is not expired, and has not been revoked (`revoked_at IS NULL`).
   - `get_current_user` then loads the user record and confirms `is_active=True`.
3. **Session Revocation (`POST /api/v1/auth/logout`)**:
   - Sets `revoked_at` on the matching `access_token` row.
   - The token becomes invalid immediately across all servers. Other sessions belonging to the same user remain unaffected.
4. **Automated Session Cleanup**:
   - Expired database tokens are cleaned up using the background CLI task:
     ```bash
     uv run python -m hr_minds.auth.tasks
     ```

---

## 🗑️ Account Deletion & Cascading Impact

A user can permanently delete their account via `DELETE /api/v1/auth/me` (requires their current password for confirmation).

### Cascading Rules & Data Preservation:
| Data Category | Outcome |
| :--- | :--- |
| **User & Password** | Deleted immediately. The email address becomes immediately eligible for re-registration. |
| **Active Sessions** | All `access_token` records for the user are deleted via database `CASCADE`. |
| **Memberships in Other Orgs** | Removed cleanly. The target organizations, their roles, and other members are untouched. |
| **Personal Organization** | Deleted along with its custom roles and pending invitations, **provided no other members exist**. |
| **Orgs With Other Members** | If other members belong to the user's personal organization, deletion is refused with `409 Conflict`. Members must be removed first. |
| **Sent Invitations** | Invitations sent by the user to other organizations remain valid (`invitation.invited_by_id` is set to `NULL`). |

---

## 👥 Multi-Tenant Organization & RBAC Integration

At signup (`POST /api/v1/auth/register`), a personal **Organization** is automatically provisioned for the new user, and they are granted the **Owner** membership.

For complete documentation on organization scoping, custom roles, permissions, and endpoint protection:
- 🧩 **[Features](Features)**: Overview of the system feature registry and permission model.
- 👥 **[RBAC](RBAC)**: Role-Based Access Control, custom roles, permissions, and multi-tenant organization scoping.
- 🔌 **[API Reference](API-Endpoints)**: Interactive endpoints, cURL examples, request schemas, and responses.

---

## ⚠️ Authentication Error Reference

| Status Code | Error Message (`detail`) | Scenario |
| :--- | :--- | :--- |
| `401 Unauthorized` | `Incorrect email or password` | Email does not exist OR password does not match (deliberately uniform) |
| `401 Unauthorized` | `Invalid or expired token` | Malformed JWT, expired JWT, or missing bearer prefix |
| `401 Unauthorized` | `Session is revoked or expired` | Valid JWT signature, but token was logged out or expired in DB |
| `401 Unauthorized` | `User is inactive or no longer exists` | User was disabled or deleted after token issuance |
| `403 Forbidden` | `Account is disabled` | Valid email and password supplied, but account has `is_active=False` |
| `403 Forbidden` | `Incorrect password` | Incorrect password supplied to `DELETE /auth/me` |
| `409 Conflict` | `Email already registered` | Registration attempted with an already existing email address |
| `409 Conflict` | `Your organization still has members...` | Deleting account while personal org contains other active members |
