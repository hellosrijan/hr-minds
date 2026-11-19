import pytest
from evals.metrics import precision_at_k, recall_at_k


def test_recall_at_k_perfect():
    retrieved = ["a", "b", "c", "d"]
    relevant = {"a", "b"}
    assert recall_at_k(retrieved, relevant, k=2) == 1.0
    assert recall_at_k(retrieved, relevant, k=4) == 1.0


def test_recall_at_k_partial():
    retrieved = ["a", "x", "b", "y"]
    relevant = {"a", "b", "c", "d"}
    assert recall_at_k(retrieved, relevant, k=1) == 0.25
    assert recall_at_k(retrieved, relevant, k=2) == 0.25
    assert recall_at_k(retrieved, relevant, k=3) == 0.50
    assert recall_at_k(retrieved, relevant, k=4) == 0.50


def test_recall_at_k_empty_relevant_returns_zero():
    """Documented decision: If relevant set is empty, return 0.0."""
    retrieved = ["a", "b", "c"]
    relevant = set()
    assert recall_at_k(retrieved, relevant, k=2) == 0.0


def test_recall_at_k_invalid_k_and_empty_retrieved():
    relevant = {"a", "b"}
    assert recall_at_k([], relevant, k=5) == 0.0
    assert recall_at_k(["a", "b"], relevant, k=0) == 0.0
    assert recall_at_k(["a", "b"], relevant, k=-1) == 0.0


def test_precision_at_k_perfect():
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b", "c"}
    assert precision_at_k(retrieved, relevant, k=2) == 1.0
    assert precision_at_k(retrieved, relevant, k=3) == 1.0


def test_precision_at_k_partial():
    retrieved = ["a", "x", "b", "y"]
    relevant = {"a", "b"}
    assert precision_at_k(retrieved, relevant, k=1) == 1.0
    assert precision_at_k(retrieved, relevant, k=2) == 0.5
    assert precision_at_k(retrieved, relevant, k=4) == 0.5


def test_precision_at_k_divides_unconditionally_by_k():
    """Documented decision: precision@k divides unconditionally by k even if len(retrieved) < k."""
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b", "c"}
    # 3 retrieved, all 3 relevant, but k=5 -> 3/5 = 0.60
    assert precision_at_k(retrieved, relevant, k=5) == 0.60


def test_precision_at_k_invalid_k_and_empty_retrieved():
    relevant = {"a", "b"}
    assert precision_at_k([], relevant, k=5) == 0.0
    assert precision_at_k(["a", "b"], relevant, k=0) == 0.0
    assert precision_at_k(["a", "b"], relevant, k=-2) == 0.0
