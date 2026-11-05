# HR Minds API

HR management and Agentic RAG platform built with FastAPI, async SQLAlchemy, Alembic and PostgreSQL.

> This wiki is generated from the `wiki/` folder of the main repository. Edit it there, not on GitHub — direct wiki edits are overwritten on the next sync.

## Pages

| Page | What it covers |
| :--- | :--- |
| [Development Setup](Development-Setup) | Install, configure `.env`, run the API locally |
| [Architecture](Architecture) | Project layout, settings, database base classes, routing, logging |
| [Authentication](Authentication) | Argon2 passwords, JWT sessions, logout, RBAC `require()` |
| [API Endpoints](API-Endpoints) | Every `/api/v1` endpoint |
| [Database Migrations](Database-Migrations) | Alembic workflow and commands |

## Module status

| Module | Status |
| :--- | :--- |
| Project setup, ORM & migrations | Done |
| Auth (login, logout, RBAC) | Done |
| Media upload (local storage) | Planned — `FeatureSlug.MEDIA` registered, no router yet |
| Recruitment (Agentic RAG resume filtering) | Planned |
