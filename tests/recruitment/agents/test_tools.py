"""
The recruitment tools, through the assistant: creating a posting waits for approval, a
rejected one is never saved, and reading postings needs no approval.
"""

import pytest
from langchain_core.messages import AIMessage

from hr_minds.conversation.agents.loop import get_chat_model
from hr_minds.main import app
from tests.fake_llm import ScriptedModel
from tests.media.router.test_local_media_scan import sse_events

CONVERSATIONS = "/api/v1/conversations"
POSTINGS = "/api/v1/recruitment/job-postings"
SCANS = "/api/v1/media/local-scans"

POSTING = {
    "company_name": "Acme Corp",
    "title": "Backend Engineer",
    "description": "Build the HR Minds API.",
    "skills": [{"name": "Python", "must_have": True, "min_years": 3}],
}


def asks_for(name: str, args: dict, call_id: str = "call_1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"id": call_id, "name": name, "args": args}])


@pytest.fixture
def use_model():
    def _use(model):
        app.dependency_overrides[get_chat_model] = lambda: model

    yield _use
    app.dependency_overrides.pop(get_chat_model, None)


async def send(client, headers, cid, content) -> list[tuple[str, dict]]:
    r = await client.post(f"{CONVERSATIONS}/{cid}/messages", json={"content": content}, headers=headers)
    assert r.status_code == 200, r.text
    return sse_events(r.text)


async def start(client, headers) -> int:
    r = await client.post(CONVERSATIONS, json={}, headers=headers)
    return r.json()["id"]


async def posting_count(client, headers) -> int:
    return (await client.get(POSTINGS, headers=headers)).json()["total"]


@pytest.mark.anyio
async def test_creating_a_posting_waits_for_approval_then_saves_it(client, signup, use_model):
    headers, _ = await signup("alice")
    cid = await start(client, headers)
    use_model(ScriptedModel(asks_for("recruitment_create_job_posting", POSTING), AIMessage(content="Posting saved.")))

    events = await send(client, headers, cid, "Create a backend posting")
    assert events[-1][0] == "approval_required"
    assert events[-1][1]["tool"] == "recruitment_create_job_posting"
    assert await posting_count(client, headers) == 0  # nothing saved before approval

    r = await client.post(f"{CONVERSATIONS}/{cid}/approvals", json={"approve": True}, headers=headers)
    resumed = sse_events(r.text)
    assert [name for name, _ in resumed] == ["tool_result", "message", "done"]
    assert resumed[0][1]["content"].count("Backend Engineer") == 1
    assert await posting_count(client, headers) == 1


@pytest.mark.anyio
async def test_a_rejected_posting_is_never_saved(client, signup, use_model):
    headers, _ = await signup("alice")
    cid = await start(client, headers)
    use_model(ScriptedModel(asks_for("recruitment_create_job_posting", POSTING), AIMessage(content="Okay, cancelled.")))

    await send(client, headers, cid, "Create a backend posting")
    r = await client.post(f"{CONVERSATIONS}/{cid}/approvals", json={"approve": False}, headers=headers)

    assert [name for name, _ in sse_events(r.text)] == ["tool_result", "message", "done"]
    assert await posting_count(client, headers) == 0


@pytest.mark.anyio
async def test_reading_postings_needs_no_approval(client, signup, use_model):
    headers, _ = await signup("alice")
    assert (await client.post(POSTINGS, json=POSTING, headers=headers)).status_code == 201
    cid = await start(client, headers)
    use_model(ScriptedModel(asks_for("recruitment_list_job_postings", {}), AIMessage(content="One posting.")))

    events = await send(client, headers, cid, "What jobs do we have?")

    assert [name for name, _ in events] == ["message", "tool_call", "tool_result", "message", "done"]
    assert "Backend Engineer" in events[2][1]["content"]


@pytest.mark.anyio
async def test_updating_a_posting_waits_for_approval(client, signup, use_model):
    headers, _ = await signup("alice")
    posting_id = (await client.post(POSTINGS, json=POSTING, headers=headers)).json()["id"]
    cid = await start(client, headers)
    args = {"job_posting_id": posting_id, "title": "Senior Backend Engineer"}
    use_model(ScriptedModel(asks_for("recruitment_update_job_posting", args), AIMessage(content="Updated.")))

    events = await send(client, headers, cid, "Make it senior")
    assert events[-1][0] == "approval_required"
    still = (await client.get(f"{POSTINGS}/{posting_id}", headers=headers)).json()
    assert still["title"] == "Backend Engineer"  # unchanged until approved

    await client.post(f"{CONVERSATIONS}/{cid}/approvals", json={"approve": True}, headers=headers)
    changed = (await client.get(f"{POSTINGS}/{posting_id}", headers=headers)).json()
    assert changed["title"] == "Senior Backend Engineer"
    assert changed["description"] == POSTING["description"]  # fields not sent are kept


async def make_resume(client, headers, folder, name="cv.pdf") -> int:
    """Scan a folder holding one new file and return that file's resume id."""
    folder.mkdir(exist_ok=True)
    (folder / name).write_bytes(b"x")
    r = await client.post(SCANS, json={"name": folder.name, "folder_path": str(folder)}, headers=headers)
    assert r.status_code == 201, r.text
    scan_id = sse_events(r.text)[0][1]["id"]
    items = (await client.get(f"{SCANS}/{scan_id}/files", headers=headers)).json()["items"]
    return next(i["id"] for i in items if i["file_name"] == name)


async def posting_and_resume(client, headers, folder) -> tuple[int, int]:
    pid = (await client.post(POSTINGS, json=POSTING, headers=headers)).json()["id"]
    return pid, await make_resume(client, headers, folder)


async def candidates(client, headers, pid) -> list[dict]:
    return (await client.get(f"{POSTINGS}/{pid}/candidates", headers=headers)).json()["items"]


@pytest.mark.anyio
async def test_listing_resumes_needs_no_approval(client, signup, use_model, tmp_path):
    headers, _ = await signup("alice")
    await make_resume(client, headers, tmp_path / "cvs")
    cid = await start(client, headers)
    use_model(ScriptedModel(asks_for("media_list_resumes", {}), AIMessage(content="One resume.")))

    events = await send(client, headers, cid, "Which resumes do we have?")

    assert [name for name, _ in events] == ["message", "tool_call", "tool_result", "message", "done"]
    assert "cv.pdf" in events[2][1]["content"]


@pytest.mark.anyio
async def test_listing_resumes_only_shows_your_organization(client, signup, use_model, tmp_path):
    alice, _ = await signup("alice")
    bob, _ = await signup("bob")
    await make_resume(client, bob, tmp_path / "bob", name="bobs_cv.pdf")
    cid = await start(client, alice)
    use_model(ScriptedModel(asks_for("media_list_resumes", {}), AIMessage(content="None.")))

    events = await send(client, alice, cid, "Which resumes do we have?")

    assert "bobs_cv.pdf" not in events[2][1]["content"]


@pytest.mark.anyio
async def test_selecting_a_resume_waits_for_approval(client, signup, use_model, tmp_path):
    headers, _ = await signup("alice")
    pid, resume_id = await posting_and_resume(client, headers, tmp_path / "cvs")
    cid = await start(client, headers)
    args = {"job_posting_id": pid, "local_media_id": resume_id}
    use_model(ScriptedModel(asks_for("recruitment_select_candidate", args), AIMessage(content="Added.")))

    events = await send(client, headers, cid, "Add this resume")
    assert events[-1][0] == "approval_required"
    assert await candidates(client, headers, pid) == []  # nothing saved before approval

    r = await client.post(f"{CONVERSATIONS}/{cid}/approvals", json={"approve": True}, headers=headers)
    assert [name for name, _ in sse_events(r.text)] == ["tool_result", "message", "done"]
    assert [c["status"] for c in await candidates(client, headers, pid)] == ["shortlisted"]


@pytest.mark.anyio
async def test_a_rejected_selection_is_never_saved(client, signup, use_model, tmp_path):
    headers, _ = await signup("alice")
    pid, resume_id = await posting_and_resume(client, headers, tmp_path / "cvs")
    cid = await start(client, headers)
    args = {"job_posting_id": pid, "local_media_id": resume_id}
    use_model(ScriptedModel(asks_for("recruitment_select_candidate", args), AIMessage(content="Cancelled.")))

    await send(client, headers, cid, "Add this resume")
    await client.post(f"{CONVERSATIONS}/{cid}/approvals", json={"approve": False}, headers=headers)

    assert await candidates(client, headers, pid) == []


@pytest.mark.anyio
async def test_moving_a_candidate_waits_for_approval(client, signup, use_model, tmp_path):
    headers, _ = await signup("alice")
    pid, resume_id = await posting_and_resume(client, headers, tmp_path / "cvs")
    candidate_id = (await client.post(f"{POSTINGS}/{pid}/candidates", json={"local_media_id": resume_id},
                                      headers=headers)).json()["id"]
    cid = await start(client, headers)
    args = {"job_posting_id": pid, "candidate_id": candidate_id, "status": "interviewing"}
    use_model(ScriptedModel(asks_for("recruitment_update_candidate_status", args), AIMessage(content="Moved.")))

    events = await send(client, headers, cid, "Move them to interviewing")
    assert events[-1][0] == "approval_required"
    assert (await candidates(client, headers, pid))[0]["status"] == "shortlisted"

    await client.post(f"{CONVERSATIONS}/{cid}/approvals", json={"approve": True}, headers=headers)
    assert (await candidates(client, headers, pid))[0]["status"] == "interviewing"


@pytest.mark.anyio
async def test_another_organizations_posting_is_not_reachable(client, signup, use_model, tmp_path):
    alice, _ = await signup("alice")
    bob, _ = await signup("bob")
    pid, resume_id = await posting_and_resume(client, bob, tmp_path / "bob")  # Bob's posting and resume
    cid = await start(client, alice)
    args = {"job_posting_id": pid, "local_media_id": resume_id}
    use_model(ScriptedModel(asks_for("recruitment_select_candidate", args), AIMessage(content="Could not add.")))

    await send(client, alice, cid, "Add Bob's resume")
    r = await client.post(f"{CONVERSATIONS}/{cid}/approvals", json={"approve": True}, headers=alice)

    result = sse_events(r.text)[0][1]
    assert "not found" in result["content"].lower()
    assert await candidates(client, bob, pid) == []


@pytest.mark.anyio
async def test_getting_a_posting_needs_no_approval(client, signup, use_model):
    headers, _ = await signup("alice")
    posting_id = (await client.post(POSTINGS, json=POSTING, headers=headers)).json()["id"]
    cid = await start(client, headers)
    use_model(ScriptedModel(
        asks_for("recruitment_get_job_posting", {"job_posting_id": posting_id}),
        AIMessage(content="Details retrieved."),
    ))

    events = await send(client, headers, cid, f"Show details for posting {posting_id}")

    assert [name for name, _ in events] == ["message", "tool_call", "tool_result", "message", "done"]
    assert "Acme Corp" in events[2][1]["content"]
    assert "Python" in events[2][1]["content"]


@pytest.mark.anyio
async def test_new_message_cancels_pending_approval(client, signup, use_model):
    headers, _ = await signup("alice")
    cid = await start(client, headers)
    use_model(ScriptedModel(
        asks_for("recruitment_create_job_posting", POSTING),
        AIMessage(content="Never mind, how can I help you now?"),
    ))

    events = await send(client, headers, cid, "Create a backend posting")
    assert events[-1][0] == "approval_required"

    # Sending a new message clears the checkpointer thread and cancels the pending approval
    events2 = await send(client, headers, cid, "Cancel that, let's do something else")
    assert events2[-1][0] == "done"

    # Attempting to submit approval now fails because the interrupt state is gone
    r = await client.post(f"{CONVERSATIONS}/{cid}/approvals", json={"approve": True}, headers=headers)
    assert sse_events(r.text) == [("error", {"detail": "No approval is pending for this conversation."})]
    assert await posting_count(client, headers) == 0

