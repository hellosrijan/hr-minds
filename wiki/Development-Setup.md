# Development Setup

## Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker & Docker Compose

---

## Local Setup Steps

```bash
# 1. Clone repository
git clone https://github.com/hellosrijan/hr-minds.git
cd hr-minds

# 2. Configure environment
cp .env.example .env
# Edit .env to set POSTGRES_PASSWORD and SECRET_KEY

# 3. Start the PostgreSQL and Qdrant (vector database) containers
docker compose up -d

# 4. Install dependencies
uv sync

# 5. Run database migrations
uv run alembic upgrade head

# 6. Synchronize system features to the database
uv run python -m hr_minds.auth.cli sync-features

# 7. Start development server
uv run fastapi dev
```

Interactive documentation:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🛠️ CLI Utilities & Scheduled Tasks

### 1. Feature Registry Sync
Whenever `FeatureSlug` or `FEATURES` in `src/hr_minds/settings/features.py` is updated, sync the definitions and default actions (`create`, `read`, `update`, `delete`) to the database:
```bash
uv run python -m hr_minds.auth.cli sync-features
```

### 2. Create Superuser
Interactive command to create an administrative user with `is_superuser=True`:
```bash
uv run python -m hr_minds.auth.cli create-superuser \
    --email admin@example.com --first-name Admin --last-name User
```

### 3. Cleanup Expired Sessions
Purges expired `access_token` records from the database. Run this via a system cron job or task runner:
```bash
uv run python -m hr_minds.auth.tasks
```

### 4. Interactive API Shell
`scripts/hr_shell.py` is a single-file, menu-driven terminal UI for trying the running API by hand: create accounts, log in, switch organizations, manage roles (permissions as a checklist) and members, send invitations, scan resume folders with live progress, chat, or send any raw request.
```bash
uv run python scripts/hr_shell.py                                 # opens the main menu
uv run python scripts/hr_shell.py --server http://host:8000       # point it at another API
```
Arrow keys move, Enter picks, Ctrl-C goes back one menu (and quits from the main menu). Things like roles, organizations and folders are picked from lists rather than typed as ids. The session (server, token, active org) is saved in `~/.hr_minds_shell.json`, so you stay logged in between runs; passwords are prompted, or read from `HR_PASSWORD` when set. It needs the `dev` dependency group (`questionary`; `rich` comes with FastAPI).

---

## 📮 Postman Setup & Collection Automation

The project includes Postman support for seamless local API testing.

### 1. Environment Variables
Create a **Development** environment in Postman with the following keys:

| Variable | Initial Value | Description |
| :--- | :--- | :--- |
| `base_url` | `http://127.0.0.1:8000/api/v1` | Root API path |
| `access_token` | *(leave empty)* | Automatically populated by login requests |
| `auth_email` | `user@example.com` | Credentials for automated token refresh |
| `auth_password` | `your_password` | Password for automated token refresh |

### 2. Token Persistence Script
In the **Generate Token** (`POST /auth/token`) request under the **Tests** tab, the token is saved into both the active environment and collection variables:

```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Save access_token for later requests", function () {
    var token = pm.response.json().access_token;
    pm.environment.set("access_token", token);
    pm.collectionVariables.set("access_token", token);
});
```

### 3. Automated 401 Token Refresh (Collection-Level Script)
To avoid manual logins when tokens expire after 30 minutes, add this script to the **Tests** tab of your root **HR Minds** collection:

```javascript
if (pm.response.code === 401 && !pm.info.requestName.includes("Generate Token")) {
    const baseUrl = pm.environment.get("base_url") || "http://127.0.0.1:8000/api/v1";
    const username = pm.environment.get("auth_email") || "margret_rodriguez@hotmail.com";
    const password = pm.environment.get("auth_password") || "securepassword@123";

    console.log("401 Unauthorized detected. Refreshing token...");

    pm.sendRequest({
        url: baseUrl + "/auth/token",
        method: "POST",
        header: { "Content-Type": "application/x-www-form-urlencoded" },
        body: {
            mode: "urlencoded",
            urlencoded: [
                { key: "username", value: username },
                { key: "password", value: password }
            ]
        }
    }, function (err, res) {
        if (!err && res.code === 200) {
            const newToken = res.json().access_token;
            pm.environment.set("access_token", newToken);
            pm.collectionVariables.set("access_token", newToken);
            console.log("Token refreshed! Retrying: " + pm.info.requestName);
            pm.execution.setNextRequest(pm.info.requestId);
        }
    });
}
```

---

## 🧪 Testing

Run the test suite with pytest:

```bash
uv run pytest
```

### Test Database Isolation:
- Tests connect to PostgreSQL using `DATABASE_URL` and create a dedicated, isolated test database: `hr_minds_test`.
- Database tables are dropped and rebuilt per test session using `NullPool`.
- `sync_features` is executed automatically in `tests/conftest.py` so feature permissions are ready.
- Helpers and fixtures such as `signup("alice")` provision temporary users and organizations on the fly.

---

## ⚙️ Environment Variables Reference

Configured in `src/hr_minds/settings/config.py` with `.env` interpolation:

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `PROJECT_NAME` | `HR Minds API` | Application title in OpenAPI docs |
| `VERSION` | `1.0.0` | API version string |
| `DESCRIPTION` | see config | API description |
| `DEBUG` | `false` | Enables SQL echoing & verbose logging; disables JSON file log |
| `DOCS_URL` / `REDOC_URL` / `OPENAPI_URL` | `/docs`, `/redoc`, `/openapi.json` | Documentation endpoints |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | — | Used by Docker Compose |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` | `localhost`, `5432`, `hr_minds` | Database connection parameters |
| `DATABASE_URL` | **Required** | `postgresql+asyncpg://...` format |
| `SECRET_KEY` | **Required** | Cryptographic key used to sign session JWTs |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Lifespan of access tokens |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | optional | Reserved for future S3 media upload |
| `AWS_S3_BUCKET_NAME` / `AWS_REGION` | optional | Reserved for future S3 media upload |
| `OPENAI_API_KEY` | optional | Reserved for Agentic RAG resume filtering |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector database for resume search (dashboard at `/dashboard`); Docker Compose also reads optional `QDRANT_PORT` |
