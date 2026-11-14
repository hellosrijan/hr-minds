"""
Job postings: org-scoped CRUD, requirements replaced as a whole list on update.
"""

import pytest
from sqlalchemy import func, select

from hr_minds.recruitment.models import JobPosting, JobRequirement
from tests.auth.router.test_rbac import in_org, join, make_role

pytestmark = pytest.mark.anyio

POSTINGS = "/api/v1/recruitment/job-postings"
ALL_ACTIONS = ["create", "read", "update", "delete"]


async def create(client, headers, title="Backend Engineer", description="We need a backend engineer.", requirements=None):
    body = {"title": title, "description": description}
    if requirements is not None:
        body["requirements"] = requirements
    r = await client.post(POSTINGS, json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_get_update_delete(client, signup):
    headers, _ = await signup("alice")
    posting = await create(client, headers, requirements=[
        {"text": "5+ years Python", "must_have": True},
        {"text": "Kubernetes", "must_have": False},
    ])
    assert posting["created_by_email"] == "alice@example.com"
    assert [(r["text"], r["must_have"]) for r in posting["requirements"]] == [
        ("5+ years Python", True), ("Kubernetes", False),
    ]
    pid = posting["id"]

    assert (await client.get(f"{POSTINGS}/{pid}", headers=headers)).json()["id"] == pid

    r = await client.patch(f"{POSTINGS}/{pid}", json={"title": "Senior Backend Engineer"}, headers=headers)
    assert r.status_code == 200
    updated = r.json()
    assert updated["title"] == "Senior Backend Engineer"
    assert len(updated["requirements"]) == 2  # untouched: requirements wasn't sent

    r = await client.patch(f"{POSTINGS}/{pid}", json={"requirements": [{"text": "Go", "must_have": True}]}, headers=headers)
    assert [(r_["text"], r_["must_have"]) for r_ in r.json()["requirements"]] == [("Go", True)]

    r = await client.patch(f"{POSTINGS}/{pid}", json={"requirements": []}, headers=headers)
    assert r.json()["requirements"] == []

    assert (await client.delete(f"{POSTINGS}/{pid}", headers=headers)).status_code == 204
    assert (await client.get(f"{POSTINGS}/{pid}", headers=headers)).status_code == 404


async def test_requirements_default_to_empty(client, signup):
    headers, _ = await signup("alice")
    assert (await create(client, headers))["requirements"] == []


async def test_deleting_a_posting_deletes_its_requirements(client, signup, db):
    headers, _ = await signup("alice")
    pid = (await create(client, headers, requirements=[{"text": "SQL"}, {"text": "Docker"}]))["id"]

    async def requirement_count() -> int:
        return await db.scalar(select(func.count()).select_from(JobRequirement).where(JobRequirement.job_posting_id == pid))

    assert await requirement_count() == 2
    await client.delete(f"{POSTINGS}/{pid}", headers=headers)
    assert await requirement_count() == 0
    assert await db.get(JobPosting, pid) is None


async def test_isolation_across_organizations(client, signup):
    alice, alice_org = await signup("alice")
    bob, bob_org = await signup("bob")
    pid = (await create(client, alice))["id"]

    assert (await client.get(f"{POSTINGS}/{pid}", headers=bob)).status_code == 404
    assert (await client.patch(f"{POSTINGS}/{pid}", json={"title": "x"}, headers=bob)).status_code == 404
    assert (await client.delete(f"{POSTINGS}/{pid}", headers=bob)).status_code == 404
    assert (await client.get(POSTINGS, headers=bob)).json()["total"] == 0
    assert (await client.get(POSTINGS, headers=alice)).json()["total"] == 1

    # Not visible under the wrong org header either, even for the same user.
    role = await make_role(client, bob, bob_org, "Viewer", {"recruitment": ["read"]})
    await join(client, bob, bob_org, role, alice, "alice@example.com")
    assert (await client.get(f"{POSTINGS}/{pid}", headers=in_org(alice, bob_org))).status_code == 404


async def test_permissions_gate_each_endpoint(client, signup):
    alice, org = await signup("alice")
    bob, _ = await signup("bob")
    reader = await make_role(client, alice, org, "Reader", {"recruitment": ["read"]})
    await join(client, alice, org, reader, bob, "bob@example.com")
    as_reader = in_org(bob, org)

    assert (await client.get(POSTINGS, headers=as_reader)).status_code == 200
    assert (await client.post(POSTINGS, json={"title": "x", "description": "y"}, headers=as_reader)).status_code == 403
    assert (await client.patch(f"{POSTINGS}/1", json={"title": "x"}, headers=as_reader)).status_code == 403
    assert (await client.delete(f"{POSTINGS}/1", headers=as_reader)).status_code == 403
    assert (await client.get(POSTINGS)).status_code == 401


async def test_input_limits(client, signup):
    headers, _ = await signup("alice")
    for body in ({"title": "", "description": "x"}, {"title": "x" * 256, "description": "x"},
                 {"title": "x", "description": ""}, {"title": "x"}):
        assert (await client.post(POSTINGS, json=body, headers=headers)).status_code == 422

    too_many = [{"text": f"req {i}"} for i in range(51)]
    assert (await client.post(POSTINGS, json={"title": "x", "description": "y", "requirements": too_many},
                              headers=headers)).status_code == 422


async def test_pagination(client, signup):
    headers, _ = await signup("alice")
    ids = [(await create(client, headers, title=f"Role {i}"))["id"] for i in range(5)]

    page = (await client.get(POSTINGS, params={"page": 2, "page_size": 2}, headers=headers)).json()
    assert (page["total"], page["page"], page["total_pages"]) == (5, 2, 3)
    assert [p["id"] for p in page["items"]] == ids[2:4]  # oldest first, stable order
    assert (await client.get(POSTINGS, params={"page": 9}, headers=headers)).json()["items"] == []
    for bad in ({"page": 0}, {"page_size": 0}, {"page_size": 101}):
        assert (await client.get(POSTINGS, params=bad, headers=headers)).status_code == 422
