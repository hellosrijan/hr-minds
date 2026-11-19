import json
import re
from pathlib import Path

import docx
import pymupdf4llm
import pytest
from scripts.candidate_data import CANDIDATES
from scripts.generate_test_dataset import generate_all, get_chrome_path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "test_dataset"
CANONICAL_SYNONYMS = {
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "reactjs": "React",
    "react.js": "React",
    "react": "React",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
}


def canonicalize(name: str) -> str:
    cleaned = name.strip().lower()
    return CANONICAL_SYNONYMS.get(cleaned, name.strip())


@pytest.fixture(scope="session")
def resumes_dir(tmp_path_factory):
    """Session-scoped fixture providing the 30 generated resumes."""
    real_resumes = DATA_DIR / "resumes"
    if real_resumes.is_dir() and len(list(real_resumes.glob("resume_*.*"))) == 30:
        return real_resumes

    try:
        chrome_path = get_chrome_path()
    except RuntimeError as e:
        pytest.skip(str(e))

    tmp_dataset = tmp_path_factory.mktemp("test_dataset")
    _, generated_resumes = generate_all(dataset_dir=tmp_dataset, chrome_path=chrome_path)
    return generated_resumes


def test_file_counts_and_split(resumes_dir):
    files = sorted(resumes_dir.glob("resume_*.*"))
    assert len(files) == 30

    pdfs = [f for f in files if f.suffix == ".pdf"]
    docxs = [f for f in files if f.suffix == ".docx"]
    assert len(pdfs) == 15
    assert len(docxs) == 15

    for idx, f in enumerate(files, start=1):
        expected_stem = f"resume_{idx:03d}"
        assert f.stem == expected_stem
        if idx % 2 == 1:
            assert f.suffix == ".pdf"
        else:
            assert f.suffix == ".docx"
        assert f.stat().st_size > 1000


def test_metadata_integrity():
    with open(DATA_DIR / "candidates_metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)

    assert len(metadata) == 30

    for c in metadata:
        total_exp = c["total_experience_years"]
        assert total_exp > 0
        for s in c["skills"]:
            assert s["years"] <= total_exp, (
                f"Candidate {c['candidate_id']}: skill {s['name']} years ({s['years']}) exceeds total exp ({total_exp})"
            )

    # Check that sum of dated roles strictly equals total experience
    for c in CANDIDATES:
        total_months = 0
        for r in c["roles"]:
            sy, sm = map(int, r["start_date"].split("-"))
            ey, em = map(int, r["end_date"].split("-"))
            total_months += (ey - sy) * 12 + (em - sm)
        calc_years = round(total_months / 12.0, 2)
        expected_years = round(c["total_experience_years"], 2)
        assert calc_years == expected_years, (
            f"Candidate {c['candidate_id']}: dated roles sum to {calc_years} yrs, expected {expected_years}"
        )


def test_all_90_tiers_recomputed_match_ground_truth():
    with open(DATA_DIR / "job_postings.json", encoding="utf-8") as f:
        postings = json.load(f)

    with open(DATA_DIR / "candidates_metadata.json", encoding="utf-8") as f:
        candidates = json.load(f)

    with open(DATA_DIR / "ground_truth.json", encoding="utf-8") as f:
        ground_truth = json.load(f)

    for p in postings:
        pid = p["id"]
        anchor = canonicalize(p["anchor_skill"])
        must_haves = {
            canonicalize(s["name"]): s.get("min_years")
            for s in p["skills"]
            if s.get("must_have")
        }
        e_min = p["experience_min_years"]
        e_max = p["experience_max_years"]

        for c in candidates:
            cid = c["candidate_id"]
            total_exp = c["total_experience_years"]
            cand_skills = {}
            for s in c["skills"]:
                cname = canonicalize(s["name"])
                cand_skills[cname] = max(cand_skills.get(cname, 0.0), s["years"])

            # 1. STRONG CHECK
            exp_in_range = e_min <= total_exp <= e_max
            has_all_must_haves = all(m in cand_skills for m in must_haves)
            meets_all_min_years = all(
                cand_skills.get(m, 0.0) >= min_y
                for m, min_y in must_haves.items()
                if min_y is not None
            )

            if exp_in_range and has_all_must_haves and meets_all_min_years:
                tier = "strong"
            else:
                # 2. PARTIAL CHECK
                has_anchor = cand_skills.get(anchor, 0.0) >= 1.0
                has_sufficient_exp = total_exp >= (e_min - 2.0)
                possessed = [m for m in must_haves if m in cand_skills]
                ratio_met = (len(possessed) / len(must_haves)) >= 0.60
                tenure_ok = all(
                    cand_skills[m] >= max(1.0, (must_haves[m] - 2.0) if must_haves[m] else 1.0)
                    for m in possessed
                )
                if has_anchor and has_sufficient_exp and ratio_met and tenure_ok:
                    tier = "partial"
                else:
                    tier = "irrelevant"

            expected_tier = ground_truth[pid]["tiers_by_candidate"][cid]
            assert tier == expected_tier, (
                f"Mismatch for {pid} x {cid}: rule computed '{tier}', ground truth expects '{expected_tier}'"
            )


def test_text_matches_metadata_whole_word(resumes_dir):
    with open(DATA_DIR / "candidates_metadata.json", encoding="utf-8") as f:
        candidates = json.load(f)

    for c in candidates:
        fname = c["file_name"]
        path = resumes_dir / fname

        if c["format"] == "pdf":
            text = pymupdf4llm.to_markdown(str(path))
        else:
            doc = docx.Document(path)
            parts = [p.text for p in doc.paragraphs]
            for t in doc.tables:
                for row in t.rows:
                    for cell in row.cells:
                        parts.extend([p.text for p in cell.paragraphs])
            text = "\n".join(parts)

        # Whole-word regex check for all skills
        for s in c["skills"]:
            sname = s["name"]
            pattern = r"\b" + re.escape(sname) + r"\b"
            match = re.search(pattern, text)
            assert match, f"{fname}: skill '{sname}' not found with whole-word regex"

    # Specific hard cases
    # Candidate 003: Postgres present, PostgreSQL absent
    c003_text = pymupdf4llm.to_markdown(str(resumes_dir / "resume_003.pdf"))
    assert re.search(r"\bPostgres\b", c003_text)
    assert not re.search(r"\bPostgreSQL\b", c003_text)

    # Candidate 011: ReactJS and TS present, React and TypeScript absent
    c011_text = pymupdf4llm.to_markdown(str(resumes_dir / "resume_011.pdf"))
    assert re.search(r"\bReactJS\b", c011_text)
    assert re.search(r"\bTS\b", c011_text)
    assert not re.search(r"\bReact\b", c011_text)
    assert not re.search(r"\bTypeScript\b", c011_text)

    # Candidate 018: K8s present, Kubernetes absent
    doc018 = docx.Document(resumes_dir / "resume_018.docx")
    t018 = "\n".join([p.text for p in doc018.paragraphs] + [c.text for t in doc018.tables for r in t.rows for c in r.cells])
    assert re.search(r"\bK8s\b", t018)
    assert not re.search(r"\bKubernetes\b", t018)

    # Candidate 006: Docker absent from skills list, present in experience bullets
    doc006 = docx.Document(resumes_dir / "resume_006.docx")
    table_skills_text = "\n".join([c.text for t in doc006.tables for r in t.rows for c in r.cells])
    assert not re.search(r"\bDocker\b", table_skills_text)
    body_text = "\n".join([p.text for p in doc006.paragraphs])
    assert re.search(r"\bDocker\b", body_text)


def test_pdf_no_header_footer(resumes_dir):
    for f in resumes_dir.glob("*.pdf"):
        text = pymupdf4llm.to_markdown(str(f))
        assert "file:///" not in text, f"{f.name} contains 'file:///' header/footer URL"


def test_docx_headings_and_tables(resumes_dir):
    with open(DATA_DIR / "candidates_metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)

    for c in metadata:
        if c["format"] != "docx":
            continue

        doc = docx.Document(resumes_dir / c["file_name"])
        heading_paras = [p for p in doc.paragraphs if p.style.name.startswith("Heading")]
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    heading_paras.extend([p for p in cell.paragraphs if p.style.name.startswith("Heading")])

        if c["docx_heading_style"] == "true_headings":
            assert len(heading_paras) > 0, f"{c['file_name']} expected true_headings but found none"
        else:
            assert len(heading_paras) == 0, f"{c['file_name']} expected plain_styled but found {len(heading_paras)} Heading styles"

        if c["layout"] in ("two_column", "table"):
            assert len(doc.tables) > 0, f"{c['file_name']} expected at least one table for layout {c['layout']}"


@pytest.mark.anyio
async def test_public_media_scanner_endpoint(client, signup, resumes_dir):
    """Test scanner integration through the public endpoint POST /api/v1/media/local-scans."""
    headers, _ = await signup("recruiter_tester")
    resp = await client.post(
        "/api/v1/media/local-scans",
        json={"name": "Test Dataset Scan", "folder_path": str(resumes_dir)},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    # Parse SSE stream
    events = []
    for block in resp.text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields and "data" in fields:
            events.append((fields["event"], json.loads(fields["data"])))

    assert len(events) > 0
    event_names = [e for e, _ in events]
    assert "registered" in event_names
    assert "summary" in event_names

    summary = events[-1][1]
    assert summary["total"] == 30
    assert summary["pdf"] == 15
    assert summary["document"] == 15
