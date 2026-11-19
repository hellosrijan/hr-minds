import json
from pathlib import Path

import pytest
from hr_minds.recruitment.schemas.job_posting import JobPostingCreate

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "test_dataset"


def test_job_postings_schema_validation():
    postings_path = DATA_DIR / "job_postings.json"
    assert postings_path.is_file(), f"Missing {postings_path}"

    with open(postings_path, encoding="utf-8") as f:
        raw_postings = json.load(f)

    assert len(raw_postings) == 3

    for item in raw_postings:
        # Check posting validates through Pydantic model
        validated = JobPostingCreate.model_validate(item)
        assert validated.company_name
        assert validated.title
        assert validated.description
        assert validated.experience_min_years >= 0
        if validated.experience_max_years is not None:
            assert validated.experience_max_years >= validated.experience_min_years

        # Check skills
        assert len(validated.skills) >= 4
        must_haves = [s for s in validated.skills if s.must_have]
        assert len(must_haves) >= 3

        # Check anchor skill is recorded in raw data and in skills
        anchor = item.get("anchor_skill")
        assert anchor is not None
        skill_names = [s.name for s in validated.skills]
        assert anchor in skill_names
