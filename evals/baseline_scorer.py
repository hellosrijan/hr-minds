"""
Baseline scoring runner.

Evaluates 30 fictional resumes against 3 job postings using an OpenAI-compatible
reasoning model at temperature 0.

Run from the repo root:
    uv run python -m evals.baseline_scorer
"""

import asyncio
import json
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from evals.cache import compute_cache_key, load_cache, save_cache
from evals.config import (
    POSTINGS_FILE,
    PROMPT_VERSION,
    RESUMES_DIR,
    TEMPERATURE,
)
from evals.prompts import SYSTEM_PROMPT, build_scoring_prompt
from evals.schemas import ResumeScore
from hr_minds.conversation.agents.loop import chat_model
from hr_minds.recruitment.services.extractor import extract_text
from hr_minds.settings.llm import model_for

logger = logging.getLogger("baseline_scorer")


def clean_json_text(text: str) -> str:
    """Strip markdown code block wrappers if present."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


async def score_resume(
    model: Any,
    resume_text: str,
    posting: dict[str, Any],
) -> dict[str, Any]:
    """Score one resume against one posting. Retries once with error feedback on invalid JSON."""
    if not resume_text.strip():
        return {
            "error": "Unreadable or empty resume text",
            "score": None,
            "skills": [],
            "reason": "Document text extraction produced no content (corrupt or scanned file).",
        }

    prompt = build_scoring_prompt(resume_text, posting)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    last_raw = ""
    for attempt in range(2):
        try:
            response = await model.ainvoke(messages)
            last_raw = response.content if hasattr(response, "content") else str(response)

            clean_text = clean_json_text(last_raw)
            parsed_data = json.loads(clean_text)
            validated = ResumeScore.model_validate(parsed_data)
            return validated.model_dump()

        except Exception as err:
            if attempt == 0:
                logger.warning(f"Attempt 1 failed ({err}). Retrying once with error feedback...")
                messages.append(AIMessage(content=last_raw))
                messages.append(
                    HumanMessage(
                        content=f"Your previous response was not valid JSON or did not match the schema: {err}. Please return only the corrected JSON."
                    )
                )
            else:
                logger.error(f"Attempt 2 failed ({err}). Storing error.")
                return {
                    "error": str(err),
                    "raw_response": last_raw,
                    "score": None,
                    "skills": [],
                    "reason": f"Model failed to produce valid structured output: {err}",
                }

    return {"error": "Unknown scoring failure", "score": None}


async def score_all_postings(model_override: Any = None) -> dict[str, Any]:
    """Score every resume against every job posting sequentially and persist each result."""
    if not POSTINGS_FILE.exists():
        raise FileNotFoundError(f"Postings file not found: {POSTINGS_FILE}")
    if not RESUMES_DIR.exists():
        raise FileNotFoundError(f"Resumes directory not found: {RESUMES_DIR}")

    with open(POSTINGS_FILE, "r", encoding="utf-8") as f:
        postings = json.load(f)

    model = model_override or chat_model("reasoning").bind(temperature=TEMPERATURE)
    model_name = "test_model" if model_override else model_for("reasoning")

    cache = load_cache()
    resume_paths = sorted(RESUMES_DIR.glob("resume_*.*"))
    logger.info(f"Loaded {len(postings)} postings and {len(resume_paths)} resumes. Total pairs: {len(postings) * len(resume_paths)}")

    for posting in postings:
        posting_id = posting["id"]
        logger.info(f"--- Scoring for Posting: {posting_id} ({posting.get('title')}) ---")

        for resume_path in resume_paths:
            file_name = resume_path.name
            resume_text = extract_text(resume_path)
            cache_key = compute_cache_key(resume_text, posting, model_name, PROMPT_VERSION)

            # A cached error is retried: it was a failed call, not an answer.
            if cache_key in cache and "error" not in cache[cache_key]["result"]:
                logger.info(f"  [CACHE HIT] {posting_id} :: {file_name}")
                continue

            logger.info(f"  [SCORING]   {posting_id} :: {file_name}...")
            result = await score_resume(model, resume_text, posting)

            cache[cache_key] = {
                "posting_id": posting_id,
                "file_name": file_name,
                "model": model_name,
                "prompt_version": PROMPT_VERSION,
                "result": result,
            }
            save_cache(cache)

    logger.info(f"Scoring complete. Total cached records: {len(cache)}")
    return cache


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(score_all_postings())
