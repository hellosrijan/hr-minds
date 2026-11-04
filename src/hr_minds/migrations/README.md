# Database Migrations (Alembic)

This directory contains the database migration scripts for **HR Minds API**, managed using [Alembic](https://alembic.sqlalchemy.org/) with asynchronous support (`asyncpg`).

---

## 🛠️ Configuration & Architecture

1. **Async Engine Connection (`env.py`)**:
   - Alembic is configured to connect asynchronously using your Pydantic settings (`settings.DATABASE_URL`), keeping credentials secure without hardcoding passwords in `alembic.ini`.
2. **Model Auto-Discovery (`env.py`)**:
   - Models like `User` are explicitly imported in `env.py` and bound to `target_metadata = Base.metadata` to enable full `--autogenerate` support.
3. **Naming Conventions (`db.py`)**:
   - Constraints (`ix`, `uq`, `ck`, `fk`, `pk`) use explicit naming conventions so Alembic can safely manage and drop constraints across environments without relying on database-generated names.

---

## 🚀 Alembic Commands Guide

Always run Alembic commands through `uv` from the project root directory:

### 1. Create a New Migration (Autogenerate)
Whenever you modify, add, or delete SQLAlchemy models in your code:
```bash
uv run alembic revision --autogenerate -m "describe your model changes here"
```
*This generates a new migration script inside `src/hr_minds/migrations/versions/`.*

### 2. Apply Migrations (Upgrade)
To apply all pending migrations up to the latest version:
```bash
uv run alembic upgrade head
```

### 3. Check Current Database Revision
To check which version the database is currently on:
```bash
uv run alembic current
```

### 4. View Migration History
To see the full history of migrations:
```bash
uv run alembic history --verbose
```

### 5. Revert / Downgrade Migrations
- **Undo the last migration (`-1`)**:
  ```bash
  uv run alembic downgrade -1
  ```
- **Downgrade everything back to scratch (`base`)**:
  ```bash
  uv run alembic downgrade base
  ```
