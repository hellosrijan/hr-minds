# API Endpoints

All routes are under `/api/v1`. Interactive docs: `/docs`.

## Auth — `/api/v1/auth`

| Method | Path | Auth | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/register` | Bearer + `auth:create` (or superuser) | Create a user. Body: `email`, `first_name`, `last_name`, `password` (8–128). Returns `UserRead`, 201. 409 if email exists. |
| `POST` | `/token` | — | OAuth2 password form: `username` (email), `password`. Returns `{access_token, token_type: "bearer"}`. |
| `POST` | `/logout` | Bearer | Revokes the current token. 204. |
| `GET` | `/me` | Bearer | Current user as `UserRead`. |

`UserRead`: `id`, `email`, `first_name`, `last_name`, `created`, `modified`.

### Example

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/token \
  -d 'username=you@example.com&password=secret123' | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/auth/me
```
