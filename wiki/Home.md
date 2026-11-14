# HR Minds API

HR management and Agentic RAG platform built with FastAPI, async SQLAlchemy, Alembic and PostgreSQL.

> This wiki is generated from the `wiki/` folder of the main repository. Edit it there, not on GitHub — direct wiki edits are overwritten on the next sync.

## Pages

| Page | What it covers |
| :--- | :--- |
| [Development Setup](Development-Setup) | Install, configure `.env`, run the API locally, Postman guide |
| [Architecture](Architecture) | Project layout, settings, database base classes, routing, logging |
| [Authentication](Authentication) | Argon2 passwords, JWT sessions, account deletion, security model |
| [Features](Features) | Feature registry, permissions model, and system capability catalog |
| [RBAC](RBAC) | Role-Based Access Control: multi-tenant organization model, custom roles, escalation guards |
| [Media](Media) | Local resume scanner, host-bound discovery, SSE progress streaming, file cataloging |
| [API Reference](API-Endpoints) | Every `/api/v1` endpoint with request/response examples, errors, `X-Org-Id`, and a curl walkthrough |
| [Database Migrations](Database-Migrations) | Alembic workflow and commands |

## Module status

| Module | Status |
| :--- | :--- |
| Project setup, ORM & migrations | Done |
| Auth (login, logout) | Done |
| Organizations & RBAC (roles, members, invitations) | Done |
| Media (Local folder scanner) | Done — Host-bound directory scanner, SSE streaming, file catalog |
| Recruitment (Agentic RAG resume filtering) | Planned |
