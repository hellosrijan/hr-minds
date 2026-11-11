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


# --- DELETE /auth/me ---


async def delete_me(client, headers, password="password123"):
    return await client.request("DELETE", ME, headers=headers, json={"password": password})


async def add_member(client, owner: dict, member: dict, email: str, permissions=()) -> int:
    """Owner invites `email` into their org with a new role and the member accepts. Returns the role id."""
    role = {"name": "Staff", "permissions": [{"feature": f, "actions": a} for f, a in permissions]}
    role_id = (await client.post("/api/v1/roles", headers=owner, json=role)).json()["id"]
    r = await client.post("/api/v1/invitations", headers=owner, json={"email": email, "role_id": role_id})
    assert (await client.post(r.json()["accept_url"], headers=member)).status_code == 200
    return role_id


async def test_delete_account_needs_password_and_ends_sessions(client, signup):
    alice, _ = await signup("alice")

    assert (await delete_me(client, alice, password="wrong-password")).status_code == 403
    assert (await delete_me(client, alice)).status_code == 204
    assert (await client.get(ME, headers=alice)).status_code == 401
    assert (await login(client)).status_code == 401
    # The email is free again.
    assert (await client.post(REGISTER, json=ALICE)).status_code == 201


async def test_deleting_a_member_leaves_the_organization_intact(client, signup):
    alice, alice_org = await signup("alice")
    bob, _ = await signup("bob")
    role_id = await add_member(client, alice, bob, "bob@example.com", [("members", ["create"])])
    # Bob invites carol into alice's org, then deletes his account.
    invite = await client.post("/api/v1/invitations", headers={**bob, "X-Org-Id": alice_org},
                               json={"email": "carol@example.com", "role_id": role_id})
    assert invite.status_code == 201

    assert (await delete_me(client, bob)).status_code == 204

    members = (await client.get("/api/v1/members", headers=alice)).json()
    assert [m["user"]["email"] for m in members] == ["alice@example.com"]
    assert [r["name"] for r in (await client.get("/api/v1/roles", headers=alice)).json()] == ["Staff"]
    assert [o["id"] for o in (await client.get("/api/v1/orgs", headers=alice)).json()] == [alice_org]
    # The invitation bob sent outlives him.
    carol, _ = await signup("carol")
    assert (await client.post(invite.json()["accept_url"], headers=carol)).status_code == 200


async def test_owner_must_remove_members_before_deleting_account(client, signup):
    alice, _ = await signup("alice")
    bob, _ = await signup("bob")
    await add_member(client, alice, bob, "bob@example.com")
    bob_id = (await client.get(ME, headers=bob)).json()["id"]

    r = await delete_me(client, alice)
    assert r.status_code == 409
    assert (await client.get(ME, headers=alice)).status_code == 200  # nothing deleted

    assert (await client.delete(f"/api/v1/members/{bob_id}", headers=alice)).status_code == 204
    assert (await delete_me(client, alice)).status_code == 204
    assert (await client.get(ME, headers=bob)).status_code == 200  # bob unaffected
