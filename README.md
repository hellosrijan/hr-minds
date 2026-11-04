<div align="center">

# 🧠 HR Minds API

### *HR Management & Agentic RAG Platform*

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![uv](https://img.shields.io/badge/uv-Package%20Manager-de5fe9?style=for-the-badge&logo=astral&logoColor=white)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

*A modular HR platform built with FastAPI and PostgreSQL.*

</div>

---

## ✨ Features

- **⚡ FastAPI backend** with auto-generated interactive API docs
  - Swagger UI at `/docs`
  - ReDoc at `/redoc`
  - OpenAPI schema at `/openapi.json`
- **⚙️ Type-safe settings** using Pydantic v2 (`pydantic-settings`), loaded from `.env`
- **🔗 Auto-assembled database URL**: `DATABASE_URL` is built from `${POSTGRES_*}` variables using `${VAR}` interpolation, so credentials are defined once
- **🐘 PostgreSQL 16 in Docker** via Docker Compose, configured from the same `.env` file
- **📦 Fast dependency management** with `uv`

---

## 🛠️ Tech Stack

| Layer | Technology |
| :--- | :--- |
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Settings | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) + [python-dotenv](https://github.com/theskumar/python-dotenv) |
| Database | PostgreSQL 16 (async driver: `asyncpg`) |
| Package manager | [uv](https://github.com/astral-sh/uv) |
| Containers | Docker & Docker Compose |

---

## 📂 Project Structure

```text
hr-minds/
├── src/
│   └── hr_minds/
│       ├── main.py              # FastAPI app entrypoint
│       └── settings/
│           └── config.py        # Environment-based settings
├── docker-compose.yml           # PostgreSQL service
├── .env.example                 # Environment variable template
├── pyproject.toml               # Project metadata & dependencies
└── README.md
```

---

## 🏁 Getting Started

### Prerequisites

- [Python 3.14+](https://www.python.org/)
- [uv](https://github.com/astral-sh/uv) (`pip install uv`)
- [Docker & Docker Compose](https://www.docker.com/)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/hr-minds.git
cd hr-minds
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set your own values. The database settings are used by both Docker Compose and the app:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=hr_minds
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
```

### 3. Start PostgreSQL

```bash
docker compose up -d
```

### 4. Install dependencies

```bash
uv sync
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

## ⚙️ Configuration

All settings are read from `.env` (see `.env.example`).

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PROJECT_NAME` | `HR Minds API` | Application name shown in the docs |
| `VERSION` | `1.0.0` | API version shown in the docs |
| `DESCRIPTION` | *(see config)* | API description shown in the docs |
| `DEBUG` | `false` | Enables debug mode |
| `DOCS_URL` | `/docs` | Swagger UI path |
| `REDOC_URL` | `/redoc` | ReDoc path |
| `OPENAPI_URL` | `/openapi.json` | OpenAPI schema path |
| `POSTGRES_USER` | `postgres` | Database user (also used by Docker Compose) |
| `POSTGRES_PASSWORD` | *required* | Database password (also used by Docker Compose) |
| `POSTGRES_HOST` | `localhost` | Database host |
| `POSTGRES_PORT` | `5432` | Database port (also used by Docker Compose) |
| `POSTGRES_DB` | `hr_minds` | Database name (also used by Docker Compose) |
| `DATABASE_URL` | *required* | Full async PostgreSQL connection string |
| `SECRET_KEY` | *required* | Secret key for signing tokens |
| `ALGORITHM` | `HS256` | Token signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime in minutes |
| `AWS_ACCESS_KEY_ID` | *optional* | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | *optional* | AWS secret key |
| `AWS_S3_BUCKET_NAME` | *optional* | S3 bucket for uploads |
| `AWS_REGION` | `us-east-1` | AWS region |
| `OPENAI_API_KEY` | *optional* | OpenAI API key |

> ⚠️ Never commit your `.env` file. Use `.env.example` for shared templates.

---

## 📜 License

Distributed under the MIT License.
