import pytest
from sqlalchemy import update

from hr_minds.auth.models import User

pytestmark = pytest.mark.anyio

REGISTER = "/api/v1/auth/register"
TOKEN = "/api/v1/auth/token"
ME = "/api/v1/auth/me"
LOGOUT = "/api/v1/auth/logout"

ALICE = {"email": "alice@example.com", "first_name": "Alice", "last_name": "Test", "password": "password123"}


async def login(client, email="alice@example.com", password="password123"):
    return await client.post(TOKEN, data={"username": email, "password": password})


async def test_register_is_public_and_hides_secrets(client):
    r = await client.post(REGISTER, json=ALICE)

    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert not {"password", "is_active", "is_superuser"} & body.keys()


async def test_register_rejects_duplicate_and_invalid_input(client):
    await client.post(REGISTER, json=ALICE)

    assert (await client.post(REGISTER, json={**ALICE, "email": "ALICE@example.com"})).status_code == 409
    assert (await client.post(REGISTER, json={**ALICE, "email": "b@example.com", "password": "short"})).status_code == 422
    assert (await client.post(REGISTER, json={**ALICE, "email": "not-an-email"})).status_code == 422


async def test_login_and_me(client):
    await client.post(REGISTER, json=ALICE)
    r = await login(client, email="ALICE@example.com")  # email is case-insensitive

    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    me = await client.get(ME, headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "alice@example.com"


async def test_login_failures_are_vague(client):
    await client.post(REGISTER, json=ALICE)

    wrong_password = await login(client, password="wrong-password")
    unknown_email = await login(client, email="nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


async def test_disabled_account_cannot_log_in_or_use_old_token(client, db):
    await client.post(REGISTER, json=ALICE)
    headers = {"Authorization": f"Bearer {(await login(client)).json()['access_token']}"}
    await db.execute(update(User).values(is_active=False))
    await db.commit()

    assert (await login(client)).status_code == 403
    assert (await client.get(ME, headers=headers)).status_code == 401


async def test_me_requires_valid_token(client):
    assert (await client.get(ME)).status_code == 401
    assert (await client.get(ME, headers={"Authorization": "Bearer garbage"})).status_code == 401


async def test_logout_revokes_only_that_token(client):
    await client.post(REGISTER, json=ALICE)
    first = {"Authorization": f"Bearer {(await login(client)).json()['access_token']}"}
    second = {"Authorization": f"Bearer {(await login(client)).json()['access_token']}"}

    assert (await client.post(LOGOUT, headers=first)).status_code == 204
    assert (await client.get(ME, headers=first)).status_code == 401
    assert (await client.post(LOGOUT, headers=first)).status_code == 401
    assert (await client.get(ME, headers=second)).status_code == 200
