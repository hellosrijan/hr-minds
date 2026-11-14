<div align="center">

# 🧠 HR Minds API

### *HR Management & Agentic RAG Platform*

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![uv](https://img.shields.io/badge/uv-Package%20Manager-de5fe9?style=for-the-badge&logo=astral&logoColor=white)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

*A modular HR platform built with FastAPI, SQLAlchemy (Async), Alembic, and PostgreSQL.*

</div>

---

## ✨ Features

- **⚡ FastAPI backend** with auto-generated interactive API docs (`/docs` & `/redoc`)
- **⚙️ Type-safe settings** using Pydantic v2 (`pydantic-settings`) with `.env` interpolation
- **🐘 PostgreSQL 16 in Docker** via Docker Compose, configured from the same `.env` file
- **🔌 Asynchronous SQLAlchemy & Alembic** for robust ORM operations and database migrations
- **📦 Fast dependency management** with `uv`

---

## 📚 Documentation & Wiki

For detailed guides, architecture notes, and API references, please check our [Wiki Directory](./wiki):

- 🏠 **[Home](./wiki/Home.md)**: Overview & documentation index
- 🏗️ **[Architecture](./wiki/Architecture.md)**: Project structure & design principles
- 🔐 **[Authentication](./wiki/Authentication.md)**: Argon2 hashing, JWT database sessions, account lifecycle
- 🧩 **[Features](./wiki/Features.md)**: Feature registry and system capability model
- 👥 **[RBAC](./wiki/RBAC.md)**: Role-Based Access Control, multi-tenant organizations, and custom roles
- 📁 **[Media](./wiki/Media.md)**: Local candidate resume scanner, SSE streaming, and file cataloging
- 💬 **[Conversation](./wiki/Conversation.md)**: Central chat session store, private per user, with messages and optional context
- 🔌 **[API Reference](./wiki/API-Endpoints.md)**: Every `/api/v1` endpoint with request/response examples and errors
- 🐘 **[Database & Migrations](./wiki/Database-Migrations.md)**: Alembic setup and commands
- 🚀 **[Development Setup](./wiki/Development-Setup.md)**: Local installation & Postman configuration guide
- 📄 **[License](./wiki/License.md)**: MIT License details and permissions


---

## 🏗️ Database Architecture & Customizations

Our ORM setup (`src/hr_minds/settings/db.py`) includes standard production patterns:

1. **Auto-Generated Table Names (`snake_case`)**:
   - Models automatically derive their table names in lowercase snake_case from the class name (e.g., `User` $\rightarrow$ `user`, `SelectedCandidate` $\rightarrow$ `selected_candidate`).
2. **`TimestampMixin`**:
   - Reusable columns included across models: `id` (primary key), `created` (timestamp on insert), and `modified` (timestamp on insert & update).
3. **Predictable Naming Conventions**:
   - Custom `MetaData` naming conventions for constraints (`ix`, `uq`, `ck`, `fk`, `pk`) to ensure seamless database migrations with Alembic across different environments.
4. **Async Session Management (`get_db`)**:
   - Provides an async session dependency yielding `AsyncSession` per request.

---

## 📂 Project Structure

```text
hr-minds/
├── src/
│   └── hr_minds/
│       ├── main.py              # FastAPI app entrypoint
│       ├── settings/
│       │   ├── config.py        # Pydantic BaseSettings config
│       │   └── db.py            # Async engine, Base, TimestampMixin, get_db
│       ├── auth/
│       │   ├── models/          # User, AccessToken, RBAC and organization models
│       │   ├── router/          # auth.py, rbac.py
│       │   ├── schemas/         # auth.py, rbac.py
│       │   └── services/        # auth.py, rbac.py
│       ├── media/               # Local resume folder scanner & cataloging
│       │   ├── models/          # LocalMediaScan, LocalMedia, MediaType
│       │   ├── router/          # local_media_scan.py (SSE streaming routes)
│       │   ├── schemas/         # LocalMediaScanCreate, LocalMediaScanRead, LocalMediaRead
│       │   └── services/        # scanner.py, local_media_scan.py
│       ├── conversation/        # Central chat session storage
│       │   ├── models/          # Conversation, Message, MessageRole
│       │   ├── router/          # conversation.py
│       │   ├── schemas/         # ConversationCreate/Update/Read, MessageCreate/Read
│       │   └── services/        # conversation.py
│       └── migrations/          # Alembic database migrations
│           └── env.py           # [Custom] Alembic environment & metadata setup
├── tests/                       # pytest (uses an hr_minds_test database)
├── docker-compose.yml           # PostgreSQL and Qdrant services
├── alembic.ini                  # Alembic configuration
├── .env.example                 # Environment variable template
├── pyproject.toml               # Project metadata & dependencies
├── LICENSE                      # MIT License
└── README.md
```

---

## 🏁 Getting Started

### Prerequisites

- [Python 3.14+](https://www.python.org/)
- [uv](https://github.com/astral-sh/uv) (`pip install uv`)
- [Docker & Docker Compose](https://www.docker.com/)

### 1. Clone & Configure Environment

```bash
git clone https://github.com/hellosrijan/hr-minds.git
cd hr-minds

# Copy environment template
cp .env.example .env
```

Edit `.env` and set your credentials:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=hr_minds
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
```

### 2. Start PostgreSQL and Qdrant

```bash
docker compose up -d
```

Qdrant (the vector database for resume search) serves its dashboard at <http://localhost:6333/dashboard>.

### 3. Install Dependencies

```bash
uv sync
```

### 4. Run Database Migrations

For detailed migration workflows, commands, and configuration notes, see the [Migrations README](src/hr_minds/migrations/README).

```bash
# Generate a new migration (when models change)
uv run alembic revision --autogenerate -m "create user table"

# Apply migrations to the database
uv run alembic upgrade head

# Sync code-defined features/permissions (rerun when FEATURES changes)
uv run python -m hr_minds.auth.cli sync-features
```

### 5. Run the API

```bash
uv run fastapi dev
```

The API will be available at:

| Endpoint | URL |
| :--- | :--- |
| Root | http://127.0.0.1:8000 |
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |

---

## ⚙️ Configuration Reference

All settings are loaded from `.env`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PROJECT_NAME` | `HR Minds API` | Application name in docs |
| `VERSION` | `1.0.0` | API version |
| `DESCRIPTION` | *(see config)* | API description |
| `DEBUG` | `false` | Enables debug mode & SQL query logging |
| `DOCS_URL` | `/docs` | Swagger UI path |
| `REDOC_URL` | `/redoc` | ReDoc path |
| `OPENAPI_URL` | `/openapi.json` | OpenAPI schema path |
| `POSTGRES_USER` | `postgres` | Database user (Docker & App) |
| `POSTGRES_PASSWORD` | *required* | Database password (Docker & App) |
| `POSTGRES_HOST` | `localhost` | Database host |
| `POSTGRES_PORT` | `5432` | Database port |
| `POSTGRES_DB` | `hr_minds` | Database name |
| `DATABASE_URL` | *required* | Full async PostgreSQL connection string |
| `SECRET_KEY` | *required* | JWT token secret key |
| `ALGORITHM` | `HS256` | Token signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime |
| `AWS_ACCESS_KEY_ID` | *optional* | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | *optional* | AWS secret key |
| `AWS_S3_BUCKET_NAME` | *optional* | S3 bucket for uploads |
| `AWS_REGION` | `us-east-1` | AWS region |
| `OPENAI_API_KEY` | *optional* | OpenAI API key |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector database URL |

> ⚠️ Never commit your `.env` file. Use `.env.example` for shared templates.

---

## 📄 License

This project is licensed under the terms of the [MIT License](LICENSE).

You are free to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software, subject to the conditions in the `LICENSE` file.

