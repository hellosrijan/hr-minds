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

    page_data = (await client.get(f"{SCANS}/{scan_id}/files", headers=headers)).json()
    assert page_data["total"] == 3
    assert page_data["page"] == 1
    assert page_data["page_size"] == 20
    assert page_data["total_pages"] == 1
    files = page_data["items"]
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


async def test_list_scan_files_pagination(client, signup, tmp_path):
    headers, _ = await signup("alice")
    for name in ["1.pdf", "2.pdf", "3.pdf", "4.pdf", "5.pdf"]:
        (tmp_path / name).write_bytes(b"x")

    r = await client.post(SCANS, json={"name": "Paged Resumes", "folder_path": str(tmp_path)}, headers=headers)
    assert r.status_code == 201
    scan_id = sse_events(r.text)[0][1]["id"]

    # Default pagination (page=1, page_size=20)
    res = await client.get(f"{SCANS}/{scan_id}/files", headers=headers)
    assert res.status_code == 200
    default_data = res.json()
    assert default_data["total"] == 5
    assert default_data["page"] == 1
    assert default_data["page_size"] == 20
    assert default_data["total_pages"] == 1
    assert len(default_data["items"]) == 5

    # Page 1 with page_size=2
    res = await client.get(f"{SCANS}/{scan_id}/files?page=1&page_size=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 3
    assert len(data["items"]) == 2
    assert [f["file_name"] for f in data["items"]] == ["1.pdf", "2.pdf"]

    # Page 2 with page_size=2
    res = await client.get(f"{SCANS}/{scan_id}/files?page=2&page_size=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 2
    assert len(data["items"]) == 2
    assert [f["file_name"] for f in data["items"]] == ["3.pdf", "4.pdf"]

    # Page 3 with page_size=2 (last page, partial)
    res = await client.get(f"{SCANS}/{scan_id}/files?page=3&page_size=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 3
    assert len(data["items"]) == 1
    assert [f["file_name"] for f in data["items"]] == ["5.pdf"]

    # Page 4 (out of bounds) -> empty items, correct metadata
    res = await client.get(f"{SCANS}/{scan_id}/files?page=4&page_size=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 4
    assert len(data["items"]) == 0
    assert data["total"] == 5
    assert data["total_pages"] == 3

    # Invalid query parameters -> 422
    assert (await client.get(f"{SCANS}/{scan_id}/files?page=0", headers=headers)).status_code == 422
    assert (await client.get(f"{SCANS}/{scan_id}/files?page_size=0", headers=headers)).status_code == 422
    assert (await client.get(f"{SCANS}/{scan_id}/files?page_size=101", headers=headers)).status_code == 422

