"""Configuration constants and filesystem paths for evaluation benchmarks."""

from pathlib import Path

# Paths
EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "test_dataset"

POSTINGS_FILE = DATA_DIR / "job_postings.json"
RESUMES_DIR = DATA_DIR / "resumes"
GROUND_TRUTH_FILE = DATA_DIR / "ground_truth.json"
CACHE_FILE = DATA_DIR / "baseline_scores.json"

# Evaluation Settings
PROMPT_VERSION = "v1"
MAX_RESUME_CHARS = 8000
TEMPERATURE = 0.0
