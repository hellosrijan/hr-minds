"""
Candidate pipeline: resumes selected for a job posting, each with a status.
"""

import pytest

from tests.auth.router.test_rbac import in_org, join, make_role
from tests.media.router.test_local_media_scan import SCANS, sse_events
from tests.recruitment.router.test_job_posting import POSTINGS, create as create_posting

pytestmark = pytest.mark.anyio


async def add_resume(client, headers, tmp_path, name="resume.pdf") -> int:
    """Register a fresh scan with one file and return its LocalMedia id."""
    (tmp_path / name).write_bytes(b"x")
    r = await client.post(SCANS, json={"name": name, "folder_path": str(tmp_path)}, headers=headers)
    events = sse_events(r.text)
    scan_id = events[0][1]["id"]
    files = (await client.get(f"{SCANS}/{scan_id}/files", headers=headers)).json()["items"]
    return next(f["id"] for f in files if f["file_name"] == name)


def candidates_url(job_posting_id: int) -> str:
    return f"{POSTINGS}/{job_posting_id}/candidates"


async def test_select_list_update_remove(client, signup, tmp_path):
    headers, _ = await signup("alice")
    pid = (await create_posting(client, headers))["id"]
    media_id = await add_resume(client, headers, tmp_path)

    r = await client.post(candidates_url(pid), json={"local_media_id": media_id}, headers=headers)
    assert r.status_code == 201, r.text
    candidate = r.json()
    assert candidate["status"] == "shortlisted"
    assert candidate["resume"]["id"] == media_id
    assert candidate["selected_by_email"] == "alice@example.com"
    cid = candidate["id"]

    listed = (await client.get(candidates_url(pid), headers=headers)).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == cid

    r = await client.patch(f"{candidates_url(pid)}/{cid}", json={"status": "interviewing"}, headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "interviewing"

    assert (await client.get(candidates_url(pid), params={"status": "interviewing"}, headers=headers)).json()["total"] == 1
    assert (await client.get(candidates_url(pid), params={"status": "hired"}, headers=headers)).json()["total"] == 0

    assert (await client.delete(f"{candidates_url(pid)}/{cid}", headers=headers)).status_code == 204
    assert (await client.get(candidates_url(pid), headers=headers)).json()["total"] == 0

    # Removing the candidate never touches the resume file record itself.
    assert (await client.get(f"/api/v1/media/local-scans/{(await client.get(SCANS, headers=headers)).json()[0]['id']}/files", headers=headers)).status_code == 200


async def test_duplicate_selection_is_rejected(client, signup, tmp_path):
    headers, _ = await signup("alice")
    pid = (await create_posting(client, headers))["id"]
    media_id = await add_resume(client, headers, tmp_path)

    assert (await client.post(candidates_url(pid), json={"local_media_id": media_id}, headers=headers)).status_code == 201
    r = await client.post(candidates_url(pid), json={"local_media_id": media_id}, headers=headers)
    assert r.status_code == 409


async def test_same_resume_selectable_for_two_postings(client, signup, tmp_path):
    headers, _ = await signup("alice")
    media_id = await add_resume(client, headers, tmp_path)
    p1 = (await create_posting(client, headers, title="Job A"))["id"]
    p2 = (await create_posting(client, headers, title="Job B"))["id"]

    assert (await client.post(candidates_url(p1), json={"local_media_id": media_id}, headers=headers)).status_code == 201
    assert (await client.post(candidates_url(p2), json={"local_media_id": media_id}, headers=headers)).status_code == 201


async def test_unknown_posting_resume_and_candidate(client, signup, tmp_path):
    headers, _ = await signup("alice")
    pid = (await create_posting(client, headers))["id"]
    media_id = await add_resume(client, headers, tmp_path)

    assert (await client.post(candidates_url(999), json={"local_media_id": media_id}, headers=headers)).status_code == 404
    assert (await client.get(candidates_url(999), headers=headers)).status_code == 404
    r = await client.post(candidates_url(pid), json={"local_media_id": 999}, headers=headers)
    assert r.status_code == 404 and r.json()["detail"] == "Resume not found"
    assert (await client.patch(f"{candidates_url(pid)}/999", json={"status": "hired"}, headers=headers)).status_code == 404
    assert (await client.delete(f"{candidates_url(pid)}/999", headers=headers)).status_code == 404
    assert (await client.patch(f"{candidates_url(pid)}/1", json={"status": "bogus"}, headers=headers)).status_code == 422


async def test_cannot_select_a_resume_from_another_organization(client, signup, tmp_path):
    alice, _ = await signup("alice")
    bob, _ = await signup("bob")
    media_id = await add_resume(client, bob, tmp_path)  # bob's own resume, in bob's org
    pid = (await create_posting(client, alice))["id"]

    r = await client.post(candidates_url(pid), json={"local_media_id": media_id}, headers=alice)
    assert r.status_code == 404 and r.json()["detail"] == "Resume not found"


async def test_deleting_a_posting_deletes_its_candidates_not_the_resume(client, signup, tmp_path, db):
    headers, _ = await signup("alice")
    pid = (await create_posting(client, headers))["id"]
    media_id = await add_resume(client, headers, tmp_path)
    await client.post(candidates_url(pid), json={"local_media_id": media_id}, headers=headers)

    assert (await client.delete(f"{POSTINGS}/{pid}", headers=headers)).status_code == 204

    from hr_minds.media.models import LocalMedia
    assert await db.get(LocalMedia, media_id) is not None  # the file record survives


async def test_pruning_a_deleted_file_drops_its_selection(client, signup, tmp_path):
    """Known tradeoff (see the ponytail comment on JobCandidate): a rescan that
    removes a vanished file also removes any selections built on it."""
    headers, _ = await signup("alice")
    pid = (await create_posting(client, headers))["id"]
    (tmp_path / "gone.pdf").write_bytes(b"x")
    r = await client.post(SCANS, json={"name": "scan", "folder_path": str(tmp_path)}, headers=headers)
    scan_id = sse_events(r.text)[0][1]["id"]
    files = (await client.get(f"{SCANS}/{scan_id}/files", headers=headers)).json()["items"]
    media_id = next(f["id"] for f in files if f["file_name"] == "gone.pdf")
    await client.post(candidates_url(pid), json={"local_media_id": media_id}, headers=headers)

    (tmp_path / "gone.pdf").unlink()
    await client.post(f"{SCANS}/{scan_id}/scan", headers=headers)

    assert (await client.get(candidates_url(pid), headers=headers)).json()["total"] == 0


async def test_permissions_gate_candidate_endpoints(client, signup, tmp_path):
    alice, org = await signup("alice")
    bob, _ = await signup("bob")
    pid = (await create_posting(client, alice))["id"]
    media_id = await add_resume(client, alice, tmp_path)
    reader = await make_role(client, alice, org, "Reader", {"recruitment": ["read"]})
    await join(client, alice, org, reader, bob, "bob@example.com")
    as_reader = in_org(bob, org)

    assert (await client.get(candidates_url(pid), headers=as_reader)).status_code == 200
    assert (await client.post(candidates_url(pid), json={"local_media_id": media_id}, headers=as_reader)).status_code == 403
    assert (await client.patch(f"{candidates_url(pid)}/1", json={"status": "hired"}, headers=as_reader)).status_code == 403
    assert (await client.delete(f"{candidates_url(pid)}/1", headers=as_reader)).status_code == 403
