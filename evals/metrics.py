"""Evaluate metrics for RAG retrieval benchmarking."""

def recall_at_k(retrieved: list[str], relevant: set[str], k:int) -> float:
    """
    Calculate Recall@k against ground-truth relevant items.

    Design decisions:
    - Evaluates on strong matches only. Partial matches are tracked separately.
    - If relevant is empty (|relevant| == 0), returns 0.0 (prevents division by zero).
    - If k <= 0, returns 0.0.
    - If k > len(retrieved), evaluates across all retrieved items.

    Parameters:
        retrieved: Ordered list of retrieved candidate identifiers or filenames.
        relevant: Set of ground-truth relevant (strong match) identifiers.
        k: Cutoff rank (1-based).

    Returns:
        float: Fraction of relevant items found in top k (between 0.0 and 1.0).
    """
    if not relevant or k <=0:
        return 0.0
    
    top_k = retrieved[:k]
    # adjust duplicate words, count as 1.
    hits = len(set(top_k) & relevant)
    return hits / len(relevant)

def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """
    Calculate Precision@k against ground-truth relevant items.

    Design decisions:
    - precision@k divides unconditionally by k, even if len(retrieved) < k.
      For example, if k=5 and 3 items are returned, all 3 relevant,
      precision@5 is 3/5 = 0.60.
    - If k <= 0 or retrieved is empty, returns 0.0.

    Parameters:
        retrieved: Ordered list of retrieved candidate identifiers or filenames.
        relevant: Set of ground-truth relevant (strong match) identifiers.
        k: Cutoff rank (1-based).

    Returns:
        float: Fraction of top k items that are relevant (between 0.0 and 1.0).
    """
    if k <= 0 or not retrieved:
        return 0.0
    
    top_k = retrieved[:k]
    # adjust duplicate words, count as 1.
    hits = len(set(top_k) & relevant)
    return hits / k