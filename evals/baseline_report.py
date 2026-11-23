"""
Baseline evaluation report generator.

Reads cached scores from data/test_dataset/baseline_scores.json, compares rankings
against ground_truth.json, computes Recall@5, Recall@10, Precision@5, and validates
tier score ordering (strong > partial > irrelevant).

Run from the repo root:
    uv run python -m evals.baseline_report
"""

import json
import logging
from typing import Any

from evals.config import CACHE_FILE, GROUND_TRUTH_FILE, POSTINGS_FILE
from evals.metrics import precision_at_k, recall_at_k

logger = logging.getLogger("baseline_report")


def generate_posting_report(
    posting_id: str,
    posting_title: str,
    scores_by_file: dict[str, dict[str, Any]],
    ground_truth: dict[str, Any],
) -> dict[str, Any]:
    """Generate evaluation statistics and ranking for a single job posting."""
    strong_files = set(ground_truth.get("strong_files", []))
    partial_files = set(ground_truth.get("partial_files", []))
    irrelevant_files = set(ground_truth.get("irrelevant_files", []))

    valid_entries: list[dict[str, Any]] = []
    failed_entries: list[dict[str, Any]] = []

    for file_name, item in scores_by_file.items():
        res = item.get("result", {})
        if res.get("error") is not None or res.get("score") is None:
            failed_entries.append({"file_name": file_name, "error": res.get("error", "Unknown error")})
        else:
            tier = "UNKNOWN"
            if file_name in strong_files:
                tier = "STRONG"
            elif file_name in partial_files:
                tier = "PARTIAL"
            elif file_name in irrelevant_files:
                tier = "IRRELEVANT"

            valid_entries.append({
                "file_name": file_name,
                "score": res["score"],
                "tier": tier,
                "reason": res.get("reason", ""),
            })

    # Sort descending by score; tie-break by file_name
    valid_entries.sort(key=lambda x: (x["score"], x["file_name"]), reverse=True)

    retrieved = [entry["file_name"] for entry in valid_entries]

    r_at_5 = recall_at_k(retrieved, strong_files, 5)
    r_at_10 = recall_at_k(retrieved, strong_files, 10)
    p_at_5 = precision_at_k(retrieved, strong_files, 5)

    # Compute average scores per tier
    strong_scores = [e["score"] for e in valid_entries if e["tier"] == "STRONG"]
    partial_scores = [e["score"] for e in valid_entries if e["tier"] == "PARTIAL"]
    irrel_scores = [e["score"] for e in valid_entries if e["tier"] == "IRRELEVANT"]

    avg_strong = sum(strong_scores) / len(strong_scores) if strong_scores else 0.0
    avg_partial = sum(partial_scores) / len(partial_scores) if partial_scores else 0.0
    avg_irrel = sum(irrel_scores) / len(irrel_scores) if irrel_scores else 0.0

    tier_order_valid = avg_strong > avg_partial > avg_irrel

    return {
        "posting_id": posting_id,
        "posting_title": posting_title,
        "ranked_candidates": valid_entries,
        "failed_candidates": failed_entries,
        "metrics": {
            "recall@5": r_at_5,
            "recall@10": r_at_10,
            "precision@5": p_at_5,
        },
        "averages": {
            "strong": round(avg_strong, 2),
            "partial": round(avg_partial, 2),
            "irrelevant": round(avg_irrel, 2),
        },
        "tier_order_valid": tier_order_valid,
    }


def print_report(reports: list[dict[str, Any]]) -> None:
    """Print markdown-formatted evaluation tables and summary cards."""
    print("\n" + "=" * 80)
    print("🎯 BASELINE SCORING REPORT (Task 13)")
    print("=" * 80 + "\n")

    for rep in reports:
        print(f"📌 Posting: {rep['posting_id']} — {rep['posting_title']}")
        print("-" * 80)

        # Ranked table
        print(f"{'Rank':<5} | {'Resume File':<20} | {'Score':<6} | {'Tier':<10} | {'Reason'}")
        print("-" * 80)
        for idx, c in enumerate(rep["ranked_candidates"], start=1):
            short_reason = (c["reason"][:45] + "...") if len(c["reason"]) > 48 else c["reason"]
            print(f"{idx:<5} | {c['file_name']:<20} | {c['score']:<6} | {c['tier']:<10} | {short_reason}")

        if rep["failed_candidates"]:
            print("\n⚠️ Failed Evaluations:")
            for f in rep["failed_candidates"]:
                print(f"  - {f['file_name']}: {f['error']}")

        # Summary
        m = rep["metrics"]
        avg = rep["averages"]
        status = "✅ PASS" if rep["tier_order_valid"] else "❌ FAIL"
        print("\n📊 Metrics:")
        print(f"  Recall@5:    {m['recall@5']:.2%}  |  Recall@10: {m['recall@10']:.2%}  |  Precision@5: {m['precision@5']:.2%}")
        print(f"  Tier Averages: Strong={avg['strong']}, Partial={avg['partial']}, Irrelevant={avg['irrelevant']}")
        print(f"  Sanity Check (Strong > Partial > Irrelevant): {status}")
        print(f"  Failures: {len(rep['failed_candidates'])}\n")


def run_report() -> list[dict[str, Any]]:
    """Load cached scores, compute metrics for all postings, and print the report."""
    if not CACHE_FILE.exists():
        raise FileNotFoundError(f"Cache file not found: {CACHE_FILE}. Run baseline_scorer.py first.")
    if not GROUND_TRUTH_FILE.exists():
        raise FileNotFoundError(f"Ground truth file not found: {GROUND_TRUTH_FILE}")
    if not POSTINGS_FILE.exists():
        raise FileNotFoundError(f"Postings file not found: {POSTINGS_FILE}")

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)
    with open(GROUND_TRUTH_FILE, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)
    with open(POSTINGS_FILE, "r", encoding="utf-8") as f:
        postings = json.load(f)

    # Group cache entries by posting_id and file_name
    by_posting: dict[str, dict[str, dict[str, Any]]] = {}
    for entry in cache.values():
        pid = entry["posting_id"]
        fname = entry["file_name"]
        by_posting.setdefault(pid, {})[fname] = entry

    reports = []
    for posting in postings:
        pid = posting["id"]
        title = posting.get("title", "")
        posting_scores = by_posting.get(pid, {})
        posting_gt = ground_truth.get(pid, {})
        rep = generate_posting_report(pid, title, posting_scores, posting_gt)
        reports.append(rep)

    print_report(reports)
    return reports


if __name__ == "__main__":
    run_report()
