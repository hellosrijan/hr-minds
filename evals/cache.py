"""Persistent cache management for evaluation runs."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from evals.config import CACHE_FILE, PROMPT_VERSION

logger = logging.getLogger("evals.cache")


def compute_cache_key(
    resume_text: str,
    posting: dict[str, Any],
    model_name: str,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    """Deterministic hash of the resume text, job posting JSON, prompt version, and model."""
    posting_repr = json.dumps(posting, sort_keys=True)
    raw_key = f"{prompt_version}::{model_name}::{posting_repr}::{resume_text}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def load_cache(path: Path = CACHE_FILE) -> dict[str, Any]:
    """Load existing cached evaluations, or return an empty dict if none exist."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read cache file ({e}). Starting fresh.")
    return {}


def save_cache(cache: dict[str, Any], path: Path = CACHE_FILE) -> None:
    """Save the cache atomically using a temporary file to avoid corruption on crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    tmp_path.replace(path)
