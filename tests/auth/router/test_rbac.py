"""
Org-scoped RBAC endpoints: tenant isolation, X-Org-Id fallback, invitations,
privilege escalation.
"""

import re

import pytest

pytestmark = pytest.mark.anyio


def in_org(headers: dict, org_id: str) -> dict:
    return {**headers, "X-Org-Id": org_id}


async def make_role(client, headers, org_id, name, permissions) -> int:
    r = await client.post("/api/v1/roles", headers=in_org(headers, org_id), json={
        "name": name, "permissions": [{"feature": f, "actions": a} for f, a in permissions.items()],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def join(client, inviter, org_id, role_id, invitee, invitee_email) -> None:
    r = await client.post("/api/v1/invitations", headers=in_org(inviter, org_id),
                          json={"email": invitee_email, "role_id": role_id})
    assert r.status_code == 201, r.text
    r = await client.post(r.json()["accept_url"], headers=invitee)
    assert r.status_code == 200, r.text


async def test_orgs_lists_own_org_with_public_id(client, signup):
    alice, _ = await signup("alice")
    orgs = (await client.get("/api/v1/orgs", headers=alice)).json()
    assert len(orgs) == 1 and orgs[0]["is_owner"] and orgs[0]["role"] is None
    assert orgs[0]["name"] == "alice"
    assert re.fullmatch(r"org_alice_[a-z0-9]{10}", orgs[0]["id"])


async def test_outsider_cannot_see_org(client, signup):
    alice, alice_org = await signup("alice")
    bob, _ = await signup("bob")

    assert (await client.get("/api/v1/roles", headers=in_org(bob, alice_org))).status_code == 404
    assert (await client.get("/api/v1/roles", headers=in_org(alice, alice_org))).status_code == 200


async def test_no_header_uses_own_org(client, signup):
    alice, alice_org = await signup("alice")
    bob, _ = await signup("bob")
    await make_role(client, alice, alice_org, "Viewer", {"roles": ["read"]})

    assert [r["name"] for r in (await client.get("/api/v1/roles", headers=alice)).json()] == ["Viewer"]
    assert (await client.get("/api/v1/roles", headers=bob)).json() == []


async def test_invitation_grants_only_role_permissions(client, signup):
    alice, org = await signup("alice")
    bob, _ = await signup("bob")
    carol, _ = await signup("carol")
    viewer = await make_role(client, alice, org, "Viewer", {"roles": ["read"]})

    # The invite is bound to the invited email.
    r = await client.post("/api/v1/invitations", headers=in_org(alice, org),
                          json={"email": "bob@example.com", "role_id": viewer})
    url = r.json()["accept_url"]
    assert (await client.post(url, headers=carol)).status_code == 404
    assert (await client.post(url, headers=bob)).status_code == 200
    assert (await client.post(url, headers=bob)).status_code == 404  # single use

    assert (await client.get("/api/v1/roles", headers=in_org(bob, org))).status_code == 200
    assert (await client.get("/api/v1/members", headers=in_org(bob, org))).status_code == 403


async def test_member_cannot_escalate(client, signup):
    alice, org = await signup("alice")
    bob, _ = await signup("bob")
    alice_id = (await client.get("/api/v1/auth/me", headers=alice)).json()["id"]
    bob_id = (await client.get("/api/v1/auth/me", headers=bob)).json()["id"]

    manager = await make_role(client, alice, org, "Manager", {
        "roles": ["read", "create"], "members": ["read", "create", "update"],
    })
    admin = await make_role(client, alice, org, "Admin", {
        "roles": ["read", "create", "update", "delete"],
        "members": ["read", "create", "update", "delete"],
    })
    await join(client, alice, org, manager, bob, "bob@example.com")

    # Can't create a role with permissions bob lacks, or invite into a stronger role.
    r = await client.post("/api/v1/roles", headers=in_org(bob, org),
                          json={"name": "Editor", "permissions": [{"feature": "roles", "actions": ["update"]}]})
    assert r.status_code == 403
    r = await client.post("/api/v1/invitations", headers=in_org(bob, org),
                          json={"email": "carol@example.com", "role_id": admin})
    assert r.status_code == 403
    # Can't promote himself or touch the owner.
    r = await client.patch(f"/api/v1/members/{bob_id}", headers=in_org(bob, org), json={"role_id": admin})
    assert r.status_code == 403
    r = await client.patch(f"/api/v1/members/{alice_id}", headers=in_org(bob, org), json={"role_id": manager})
    assert r.status_code == 403
    # Within his own permissions it works.
    await make_role(client, bob, org, "Helper", {"roles": ["read"]})
