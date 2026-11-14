from types import SimpleNamespace

import pytest

from hr_minds.media.models import MediaType
from hr_minds.media.services.scanner import _walk, scan_stream


@pytest.mark.anyio
async def test_scan_refuses_folder_from_another_system(tmp_path):
    scan = SimpleNamespace(id=1, org_id=2, folder_path=str(tmp_path), hostname="some-other-machine")

    events = [e async for e in scan_stream(None, scan)]

    assert [e["event"] for e in events] == ["error"]
    assert "some-other-machine" in events[0]["detail"]


def test_walk_picks_only_resume_files(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "fake.pdf").mkdir()  # directory with a resume-like name
    for name in ["a.PDF", "b.docx", "c.doc", "sub/d.webp", "e.gif", "f.svg", "g.txt"]:
        (tmp_path / name).write_bytes(b"x")

    rows = _walk(SimpleNamespace(id=1, org_id=2, folder_path=str(tmp_path)))

    assert sorted((r["relative_path"], r["media_type"]) for r in rows) == [
        ("a.PDF", MediaType.PDF),
        ("b.docx", MediaType.DOCUMENT),
        ("c.doc", MediaType.DOCUMENT),
        ("sub/d.webp", MediaType.IMAGE),
    ]
