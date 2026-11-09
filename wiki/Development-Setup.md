# Development Setup

## Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv)
- Docker & Docker Compose

## Steps

```bash
git clone https://github.com/hellosrijan/hr-minds.git
cd hr-minds
cp .env.example .env          # then set POSTGRES_PASSWORD and SECRET_KEY
docker compose up -d          # PostgreSQL 16, reads POSTGRES_* from .env
uv sync
uv run alembic upgrade head
uv run fastapi dev            # entrypoint: hr_minds.main:app (pyproject [tool.fastapi])
```

Swagger UI: http://127.0.0.1:8000/docs · ReDoc: http://127.0.0.1:8000/redoc

## First user

Sync the code-defined features into the database (rerun whenever `FEATURES` changes):

```bash
uv run python -m hr_minds.auth.cli sync-features
```

Then sign up with `POST /api/v1/auth/register` (public; creates your own organization). A superuser can also be created from the CLI (prompts for the password, min 8 chars):

```bash
uv run python -m hr_minds.auth.cli create-superuser \
    --email you@example.com --first-name First --last-name Last
```

## Tests

```bash
uv run pytest
```

Tests create and reuse an `hr_minds_test` database on the Postgres server in `DATABASE_URL`, rebuilding its tables for every test.

`tests/` mirrors `src/hr_minds/`: tests for `auth/router/auth.py` live in `tests/auth/router/test_auth.py`, and so on. Shared fixtures (`db`, `client`, `signup`) are in `tests/conftest.py`. Files may share names because pytest runs with `--import-mode=importlib`.

## Scheduled cleanup

Expired session rows are removed by a task you run from cron:

```bash
uv run python -m hr_minds.auth.tasks
```

## Environment variables

Loaded by `src/hr_minds/settings/config.py`. `python-dotenv` runs first so `${VAR}` interpolation works inside `.env`.

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `PROJECT_NAME` | `HR Minds API` | |
| `VERSION` | `1.0.0` | |
| `DESCRIPTION` | see config | |
| `DEBUG` | `false` | SQL echo + DEBUG log level; disables JSON file logging |
| `DOCS_URL` / `REDOC_URL` / `OPENAPI_URL` | `/docs` / `/redoc` / `/openapi.json` | |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` | — | Read by `docker-compose.yml` |
| `DATABASE_URL` | **required** | `postgresql+asyncpg://...` |
| `SECRET_KEY` | **required** | JWT signing key |
| `ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_S3_BUCKET_NAME` | optional | Not used yet |
| `AWS_REGION` | `us-east-1` | Not used yet |
| `OPENAI_API_KEY` | optional | Not used yet |
