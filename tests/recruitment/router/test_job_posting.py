"""
Job postings: org-scoped CRUD, the real-world fields (company, location, experience, skills,
salary), skills replaced as a whole list on update, and range checks.
"""

import pytest
from sqlalchemy import func, select

from hr_minds.recruitment.models import JobPosting, JobSkill
from tests.auth.router.test_rbac import in_org, join, make_role

pytestmark = pytest.mark.anyio

POSTINGS = "/api/v1/recruitment/job-postings"
ALL_ACTIONS = ["create", "read", "update", "delete"]


async def create(client, headers, title="Backend Engineer", description="We need a backend engineer.", **extra):
    body = {"company_name": "Acme Corp", "title": title, "description": description, **extra}
    r = await client.post(POSTINGS, json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def skills_of(posting) -> list[tuple]:
    return [(s["name"], s["must_have"], s["min_years"]) for s in posting["skills"]]


async def test_create_get_update_delete(client, signup):
    headers, _ = await signup("alice")
    posting = await create(
        client, headers,
        department="Platform",
        employment_type="full_time",
        work_mode="hybrid",
        location_city="Bengaluru", location_region="Karnataka", location_country="India",
        experience_min_years=3, experience_max_years=7,
        salary_min=2_500_000, salary_max=3_500_000, salary_currency="INR",
        openings=2,
        skills=[
            {"name": "Python", "must_have": True, "min_years": 4},
            {"name": "Kubernetes", "must_have": False},
        ],
    )
    assert posting["created_by_email"] == "alice@example.com"
    assert (posting["company_name"], posting["work_mode"], posting["status"]) == ("Acme Corp", "hybrid", "open")
    assert (posting["location_city"], posting["location_country"]) == ("Bengaluru", "India")
    assert (posting["experience_min_years"], posting["experience_max_years"]) == (3, 7)
    assert skills_of(posting) == [("Python", True, 4), ("Kubernetes", False, None)]
    pid = posting["id"]

    assert (await client.get(f"{POSTINGS}/{pid}", headers=headers)).json()["id"] == pid

    r = await client.patch(f"{POSTINGS}/{pid}", json={"title": "Senior Backend Engineer"}, headers=headers)
    assert r.status_code == 200
    updated = r.json()
    assert updated["title"] == "Senior Backend Engineer"
    assert updated["company_name"] == "Acme Corp"  # not sent, so unchanged
    assert len(updated["skills"]) == 2  # skills not sent, so unchanged

    r = await client.patch(f"{POSTINGS}/{pid}", json={"skills": [{"name": "Go", "must_have": True}]}, headers=headers)
    assert skills_of(r.json()) == [("Go", True, None)]

    r = await client.patch(f"{POSTINGS}/{pid}", json={"skills": []}, headers=headers)
    assert r.json()["skills"] == []

    assert (await client.delete(f"{POSTINGS}/{pid}", headers=headers)).status_code == 204
    assert (await client.get(f"{POSTINGS}/{pid}", headers=headers)).status_code == 404


async def test_defaults_for_a_minimal_posting(client, signup):
    headers, _ = await signup("alice")
    posting = await create(client, headers)
    assert (posting["employment_type"], posting["work_mode"], posting["status"]) == ("full_time", "onsite", "open")
    assert (posting["experience_min_years"], posting["experience_max_years"], posting["openings"]) == (0, None, 1)
    assert (posting["department"], posting["location_city"], posting["salary_min"], posting["salary_currency"]) == (
        None, None, None, None)
    assert posting["skills"] == []


async def test_clearing_optional_fields_with_null(client, signup):
    headers, _ = await signup("alice")
    pid = (await create(client, headers, location_city="Pune", salary_min=100, salary_currency="USD",
                        experience_max_years=5))["id"]

    r = await client.patch(f"{POSTINGS}/{pid}", json={
        "location_city": None, "salary_min": None, "salary_currency": None, "experience_max_years": None,
    }, headers=headers)
    assert r.status_code == 200
    cleared = r.json()
    assert (cleared["location_city"], cleared["salary_min"], cleared["salary_currency"],
            cleared["experience_max_years"]) == (None, None, None, None)

    # Null on a field that must have a value means "leave it alone", not "clear it".
    r = await client.patch(f"{POSTINGS}/{pid}", json={"company_name": None, "openings": None}, headers=headers)
    assert (r.json()["company_name"], r.json()["openings"]) == ("Acme Corp", 1)


async def test_experience_and_salary_ranges_are_checked(client, signup):
    headers, _ = await signup("alice")
    bad = [
        {"experience_min_years": 5, "experience_max_years": 2},
        {"salary_min": 900, "salary_max": 100, "salary_currency": "USD"},
        {"salary_min": 900},  # a salary with no currency
    ]
    for extra in bad:
        r = await client.post(POSTINGS, json={"company_name": "Acme", "title": "x", "description": "y", **extra},
                              headers=headers)
        assert r.status_code == 400, extra

    pid = (await create(client, headers, experience_min_years=3))["id"]
    # The update is checked against the whole posting, not just the fields it sends.
    r = await client.patch(f"{POSTINGS}/{pid}", json={"experience_max_years": 2}, headers=headers)
    assert r.status_code == 400
    r = await client.patch(f"{POSTINGS}/{pid}", json={"salary_min": 5}, headers=headers)
    assert r.status_code == 400  # no currency
    assert (await client.get(f"{POSTINGS}/{pid}", headers=headers)).json()["experience_max_years"] is None


async def test_skills_default_to_empty(client, signup):
    headers, _ = await signup("alice")
    assert (await create(client, headers))["skills"] == []


async def test_deleting_a_posting_deletes_its_skills(client, signup, db):
    headers, _ = await signup("alice")
    pid = (await create(client, headers, skills=[{"name": "SQL"}, {"name": "Docker"}]))["id"]

    async def skill_count() -> int:
        return await db.scalar(select(func.count()).select_from(JobSkill).where(JobSkill.job_posting_id == pid))

    assert await skill_count() == 2
    await client.delete(f"{POSTINGS}/{pid}", headers=headers)
    assert await skill_count() == 0
    assert await db.get(JobPosting, pid) is None


async def test_skill_names_are_normalized_for_matching(client, signup, db):
    headers, _ = await signup("alice")
    pid = (await create(client, headers, skills=[{"name": "  PostgreSQL "}]))["id"]
    stored = await db.scalar(select(JobSkill).where(JobSkill.job_posting_id == pid))
    assert (stored.name, stored.name_normalized) == ("  PostgreSQL ", "postgresql")


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

    body = {"company_name": "Acme", "title": "x", "description": "y"}
    assert (await client.get(POSTINGS, headers=as_reader)).status_code == 200
    assert (await client.post(POSTINGS, json=body, headers=as_reader)).status_code == 403
    assert (await client.patch(f"{POSTINGS}/1", json={"title": "x"}, headers=as_reader)).status_code == 403
    assert (await client.delete(f"{POSTINGS}/1", headers=as_reader)).status_code == 403
    assert (await client.get(POSTINGS)).status_code == 401


async def test_input_limits(client, signup):
    headers, _ = await signup("alice")
    base = {"company_name": "Acme", "title": "x", "description": "y"}
    bad = [
        {**base, "title": ""}, {**base, "title": "x" * 256}, {**base, "description": ""},
        {**base, "company_name": ""}, {**base, "experience_min_years": -1}, {**base, "experience_min_years": 61},
        {**base, "salary_currency": "usd"}, {**base, "openings": 0}, {**base, "employment_type": "freelance"},
        {**base, "work_mode": "moon"}, {**base, "status": "maybe"},
        {"title": "x", "description": "y"},  # no company
    ]
    for body in bad:
        assert (await client.post(POSTINGS, json=body, headers=headers)).status_code == 422, body

    too_many = [{"name": f"skill {i}"} for i in range(51)]
    assert (await client.post(POSTINGS, json={**base, "skills": too_many}, headers=headers)).status_code == 422


async def test_pagination(client, signup):
    headers, _ = await signup("alice")
    ids = [(await create(client, headers, title=f"Role {i}"))["id"] for i in range(5)]

    page = (await client.get(POSTINGS, params={"page": 2, "page_size": 2}, headers=headers)).json()
    assert (page["total"], page["page"], page["total_pages"]) == (5, 2, 3)
    assert [p["id"] for p in page["items"]] == ids[2:4]  # oldest first, stable order
    assert (await client.get(POSTINGS, params={"page": 9}, headers=headers)).json()["items"] == []
    for bad in ({"page": 0}, {"page_size": 0}, {"page_size": 101}):
        assert (await client.get(POSTINGS, params=bad, headers=headers)).status_code == 422
