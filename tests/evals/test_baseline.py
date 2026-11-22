"""
Unit tests for Task 13 baseline scoring, extraction, caching, and reporting.

All tests run completely offline with fake LLMs (no tokens or network calls).
"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from evals.baseline_report import generate_posting_report
from evals.baseline_scorer import build_scoring_prompt, clean_json_text, score_resume
from evals.cache import compute_cache_key, load_cache, save_cache
from evals.prompts import SYSTEM_PROMPT
from evals.schemas import ResumeScore
from hr_minds.recruitment.services.extractor import extract_text
from tests.fake_llm import ScriptedModel

SAMPLE_POSTING = {
    "id": "posting_1_backend_senior",
    "title": "Senior Backend Engineer",
    "department": "Core Platform",
    "description": "Building async microservices in Python and FastAPI.",
    "experience_min_years": 5,
    "skills": [
        {"name": "Python", "must_have": True, "min_years": 5},
        {"name": "FastAPI", "must_have": True, "min_years": 3},
    ],
}

VALID_SCORE_JSON = """{
  "score": 85,
  "skills": [
    {"name": "Python", "found": true, "years_experience": 6.0, "evidence": "6 years leading backend projects in Python."},
    {"name": "FastAPI", "found": true, "years_experience": 3.5, "evidence": "Built high-concurrency FastAPI APIs."}
  ],
  "reason": "Strong match for Senior Backend Engineer with required Python and FastAPI experience."
}"""


# ---------------------------------------------------------------------------
# 1. Text Extractor Tests
# ---------------------------------------------------------------------------

def test_extract_text_pdf(tmp_path):
    pdf_path = Path("data/test_dataset/resumes/resume_001.pdf")
    if not pdf_path.exists():
        pytest.skip("Test dataset resumes not generated yet")
    text = extract_text(pdf_path)
    assert len(text) > 200
    assert "Python" in text or "Developer" in text or "Engineer" in text


def test_extract_text_docx(tmp_path):
    docx_path = Path("data/test_dataset/resumes/resume_002.docx")
    if not docx_path.exists():
        pytest.skip("Test dataset resumes not generated yet")
    text = extract_text(docx_path)
    assert len(text) > 200


def test_extract_text_corrupt_file(tmp_path):
    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"%PDF-1.4 corrupt garbage content that cannot be parsed")
    assert extract_text(corrupt_pdf) == ""

    corrupt_docx = tmp_path / "corrupt.docx"
    corrupt_docx.write_bytes(b"PK\x03\x04 not a real docx zip archive")
    assert extract_text(corrupt_docx) == ""


# ---------------------------------------------------------------------------
# 2. Prompt Builder & JSON Cleaner Tests
# ---------------------------------------------------------------------------

def test_build_scoring_prompt_xml_wrapping():
    prompt = build_scoring_prompt("System engineer with 7 years experience.", SAMPLE_POSTING)
    assert "<resume_content>" in prompt
    assert "</resume_content>" in prompt
    assert "System engineer with 7 years experience." in prompt
    assert "Senior Backend Engineer" in prompt
    assert "RULES" in SYSTEM_PROMPT


def test_build_scoring_prompt_truncates_long_resumes():
    long_text = "A" * 12000
    prompt = build_scoring_prompt(long_text, SAMPLE_POSTING)
    # The resume part should be capped at 8000
    assert "A" * 8000 in prompt
    assert "A" * 8001 not in prompt


def test_clean_json_text_markdown_fences():
    raw_markdown = f"```json\n{VALID_SCORE_JSON}\n```"
    cleaned = clean_json_text(raw_markdown)
    assert cleaned.startswith("{") and cleaned.endswith("}")

    raw_markdown_no_tag = f"```\n{VALID_SCORE_JSON}\n```"
    cleaned_no_tag = clean_json_text(raw_markdown_no_tag)
    assert cleaned_no_tag.startswith("{") and cleaned_no_tag.endswith("}")


# ---------------------------------------------------------------------------
# 3. Model Scoring & Retry Loop Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_score_resume_empty_text():
    result = await score_resume(None, "", SAMPLE_POSTING)
    assert result["score"] is None
    assert "Unreadable" in result["error"]


@pytest.mark.anyio
async def test_score_resume_success_first_try():
    model = ScriptedModel(AIMessage(content=VALID_SCORE_JSON))
    result = await score_resume(model, "Python and FastAPI engineer", SAMPLE_POSTING)

    assert result["score"] == 85
    assert len(result["skills"]) == 2
    assert result["skills"][0]["name"] == "Python"
    assert result["skills"][0]["found"] is True
    assert "error" not in result


@pytest.mark.anyio
async def test_score_resume_retry_recovers():
    # Attempt 1 returns broken JSON, Attempt 2 returns valid JSON
    model = ScriptedModel(
        AIMessage(content="Sorry, here is the result: { broken json ..."),
        AIMessage(content=VALID_SCORE_JSON),
    )
    result = await score_resume(model, "Python and FastAPI engineer", SAMPLE_POSTING)

    assert result["score"] == 85
    assert len(model.sent) == 2
    assert "Your previous response was not valid JSON" in model.sent[1][-1].content


@pytest.mark.anyio
async def test_score_resume_double_failure_stores_error():
    # Both attempts return invalid JSON
    model = ScriptedModel(
        AIMessage(content="Broken json 1"),
        AIMessage(content="Broken json 2"),
    )
    result = await score_resume(model, "Python and FastAPI engineer", SAMPLE_POSTING)

    assert result["score"] is None
    assert "error" in result
    assert result["raw_response"] == "Broken json 2"


# ---------------------------------------------------------------------------
# 4. Cache Persistence Tests
# ---------------------------------------------------------------------------

def test_cache_key_deterministic():
    key1 = compute_cache_key("resume text", SAMPLE_POSTING, "test-model", "v1")
    key2 = compute_cache_key("resume text", SAMPLE_POSTING, "test-model", "v1")
    key3 = compute_cache_key("resume text altered", SAMPLE_POSTING, "test-model", "v1")
    key4 = compute_cache_key("resume text", SAMPLE_POSTING, "test-model", "v2")

    assert key1 == key2
    assert key1 != key3
    assert key1 != key4


def test_save_and_load_cache(tmp_path):
    cache_file = tmp_path / "test_cache.json"
    cache_data = {"key_1": {"posting_id": "p1", "score": 90}}

    save_cache(cache_data, path=cache_file)
    assert cache_file.exists()

    loaded = load_cache(path=cache_file)
    assert loaded == cache_data


# ---------------------------------------------------------------------------
# 5. Report Logic & Sanity Checks Tests
# ---------------------------------------------------------------------------

def test_generate_posting_report():
    gt = {
        "strong_files": ["f1.pdf", "f2.pdf"],
        "partial_files": ["f3.docx"],
        "irrelevant_files": ["f4.docx"],
    }
    scores_by_file = {
        "f1.pdf": {"result": {"score": 95, "reason": "Expert"}},
        "f2.pdf": {"result": {"score": 90, "reason": "Great"}},
        "f3.docx": {"result": {"score": 60, "reason": "Mid"}},
        "f4.docx": {"result": {"score": 20, "reason": "Low"}},
        "f5.pdf": {"result": {"error": "JSON parse error", "score": None}},
    }

    report = generate_posting_report("p1", "Senior Engineer", scores_by_file, gt)

    # Ranking: f1 (95), f2 (90), f3 (60), f4 (20)
    assert [c["file_name"] for c in report["ranked_candidates"]] == ["f1.pdf", "f2.pdf", "f3.docx", "f4.docx"]
    # Failures: f5
    assert len(report["failed_candidates"]) == 1
    assert report["failed_candidates"][0]["file_name"] == "f5.pdf"

    # Metrics
    assert report["metrics"]["recall@5"] == 1.0  # Both f1 and f2 in top 5
    assert report["metrics"]["precision@5"] == 0.4  # 2 strong matches / 5 = 0.4

    # Tier averages
    assert report["averages"]["strong"] == 92.5
    assert report["averages"]["partial"] == 60.0
    assert report["averages"]["irrelevant"] == 20.0
    assert report["tier_order_valid"] is True
