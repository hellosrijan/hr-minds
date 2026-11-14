import json

import pytest

pytestmark = pytest.mark.anyio

SCANS = "/api/v1/media/local-scans"


def sse_events(text: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into [(event, data), ...]."""
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((fields.get("event"), json.loads(fields["data"])))
    return events


async def test_register_scan_list_rescan_delete(client, signup, tmp_path):
    headers, _ = await signup("alice")
    (tmp_path / "sub").mkdir()
    for name in ["a.pdf", "b.docx", "sub/c.png", "notes.txt"]:
        (tmp_path / name).write_bytes(b"x")

    r = await client.post(SCANS, json={"name": "Resumes", "folder_path": str(tmp_path)}, headers=headers)
    assert r.status_code == 201, r.text
    events = sse_events(r.text)
    assert [e for e, _ in events] == ["registered", "progress", "progress", "progress", "summary"]
    summary = events[-1][1]
    assert (summary["total"], summary["pdf"], summary["document"], summary["image"]) == (3, 1, 1, 1)
    assert summary["scanned_by_email"] == "alice@example.com"
    scan_id = events[0][1]["id"]

    listed = (await client.get(SCANS, headers=headers)).json()
    assert listed[0]["last_scanned_by_email"] == "alice@example.com"
    assert listed[0]["os_name"] and listed[0]["hostname"]

    assert str(tmp_path / "sub" / "c.png") in {d["file_path"] for e, d in events if e == "progress"}

    files = (await client.get(f"{SCANS}/{scan_id}/files", headers=headers)).json()
    assert sorted(f["relative_path"] for f in files) == ["a.pdf", "b.docx", "sub/c.png"]
    assert sorted(f["file_path"] for f in files) == [str(tmp_path / p) for p in ["a.pdf", "b.docx", "sub/c.png"]]

    (tmp_path / "a.pdf").unlink()
    r = await client.post(f"{SCANS}/{scan_id}/scan", headers=headers)
    assert r.status_code == 200, r.text
    assert sse_events(r.text)[-1][1]["removed"] == 1

    assert (await client.delete(f"{SCANS}/{scan_id}", headers=headers)).status_code == 204
    assert (await client.get(SCANS, headers=headers)).json() == []


async def test_bad_folder_and_unknown_scan_fail_before_streaming(client, signup, tmp_path):
    headers, _ = await signup("alice")

    r = await client.post(SCANS, json={"name": "x", "folder_path": str(tmp_path / "nope")}, headers=headers)
    assert r.status_code == 422

    assert (await client.post(f"{SCANS}/999/scan", headers=headers)).status_code == 404
