# Architecture

## Layout

```text
src/hr_minds/
├── main.py                 # FastAPI app, lifespan (sets up logging), mounts api_router
├── settings/
│   ├── config.py           # Pydantic Settings singleton: `settings`
│   ├── db.py               # async engine, AsyncSessionLocal, Base, TimestampMixin, get_db
│   ├── features.py         # FeatureSlug enum + FEATURES registry — see [Features](Features)
│   ├── logging.py          # setup_logging(): text to stdout, JSON to logs/app.log
│   └── routers.py          # api_router (prefix /api/v1) — every module router mounts here
├── auth/                   # Authentication & RBAC implementation — see [Authentication](Authentication), [RBAC](RBAC)
│   ├── router/  schemas/  services/   # each split into auth.py and rbac.py
│   ├── dependencies.py     # get_current_user, org-scoped require()
│   ├── exceptions.py
│   ├── cli.py              # create-superuser, sync-features
│   ├── tasks.py            # delete expired sessions
│   └── models/             # user, token, rbac (Feature, Permission, Role), org (Organization, Membership, Invitation)
├── media/                  # placeholder (planned)
└── migrations/             # Alembic (async)
tests/                      # pytest, mirrors src/hr_minds (tests/auth/router/test_auth.py, ...)
```

## Routing

`settings/routers.py` defines one `APIRouter(prefix="/api/v1")`. Each feature module exposes its own `router` with its own prefix (e.g. `/auth`), which is included there. `main.py` includes only `api_router`.

To add a module: create `<module>/router.py`, include it in `settings/routers.py`, add its slug to `FeatureSlug`/`FEATURES` in `settings/features.py` if it needs permissions, and run `sync-features`. Org data gets an `org_id` column; endpoints take the org from `require()` (the `X-Org-Id` header).

## Database base classes (`settings/db.py`)

- **`Base`** — table name is derived from the class name in snake_case (`SelectedCandidate` → `selected_candidate`). Its `MetaData` uses a naming convention for `ix`, `uq`, `ck`, `fk`, `pk` so Alembic gets stable constraint names.
- **`TimestampMixin`** — adds `id` (PK), `created` and `modified` (timezone-aware, server-set).
- **`get_db()`** — FastAPI dependency yielding one `AsyncSession` per request. Sessions use `expire_on_commit=False`.

## Features registry (`settings/features.py`)

`FEATURES` maps each `FeatureSlug` to a name, base path and description. Slugs are stored in the database (`feature.slug`), so renaming one needs a data migration. `DEFAULT_ACTIONS` is `create, read, update, delete`.

## Logging (`settings/logging.py`)

Called from the app lifespan. Always logs plain text to stdout. When `DEBUG` is false, also writes JSON lines to `logs/app.log`. `uvicorn.access` is set to WARNING; `sqlalchemy.engine` is INFO only in debug.
