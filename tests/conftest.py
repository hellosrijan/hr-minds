"""
Shared fixtures. Tests that touch the database run against a throwaway
`hr_minds_test` database on the server in DATABASE_URL (created if missing,
tables rebuilt per test), so the dev database is never touched.
"""

import httpx
import pytest
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from hr_minds.auth.services.rbac import sync_features
from hr_minds.main import app
from hr_minds.settings.config import settings
from hr_minds.settings.db import Base, get_db

TEST_DB = "hr_minds_test"
PASSWORD = "password123"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def sessions():
    """Session factory bound to a freshly rebuilt test database with features synced."""
    admin = create_async_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        if not await conn.scalar(text(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB}'")):
            await conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    await admin.dispose()

    engine = create_async_engine(make_url(settings.DATABASE_URL).set(database=TEST_DB), poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await sync_features(db)
    yield factory
    await engine.dispose()


@pytest.fixture
async def db(sessions):
    async with sessions() as session:
        yield session


@pytest.fixture
async def client(sessions):
    """HTTP client for the app, with get_db pointed at the test database."""

    async def test_db():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def signup(client):
    """`await signup("alice")` registers alice@example.com, logs in, returns (auth headers, own org id)."""

    async def _signup(name: str) -> tuple[dict, str]:
        email = f"{name}@example.com"
        r = await client.post("/api/v1/auth/register", json={
            "email": email, "first_name": name, "last_name": "Test", "password": PASSWORD,
        })
        assert r.status_code == 201, r.text
        r = await client.post("/api/v1/auth/token", data={"username": email, "password": PASSWORD})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        orgs = (await client.get("/api/v1/orgs", headers=headers)).json()
        return headers, orgs[0]["id"]

    return _signup
