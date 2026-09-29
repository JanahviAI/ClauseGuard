def calculate_metrics(y_true, y_pred):
    """
    Deterministic standard formulas for evaluating binary classification.
    y_true: list of int (0 or 1)
    y_pred: list of int (0 or 1)
    
    Positive class = 1 (Privacy clause)
    Negative class = 0 (Non-privacy clause)
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length.")
        
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)
    
    # Zero-division safety
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "Precision": precision,
        "Recall": recall,
        "F1": f1
    }

def calculate_cohens_kappa(labels_a, labels_b):
    """
    Cohen's Kappa for two annotators with binary labels (0/1).
    """
    if len(labels_a) != len(labels_b):
        raise ValueError("labels_a and labels_b must have the same length.")
    if not labels_a:
        raise ValueError("labels_a and labels_b must be non-empty.")

    n = len(labels_a)
    agreement = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n

    p_a_pos = sum(1 for value in labels_a if value == 1) / n
    p_a_neg = 1 - p_a_pos
    p_b_pos = sum(1 for value in labels_b if value == 1) / n
    p_b_neg = 1 - p_b_pos
    expected = (p_a_pos * p_b_pos) + (p_a_neg * p_b_neg)

    if expected == 1.0:
        return 1.0

    return (agreement - expected) / (1 - expected)

def define_baselines():
    """
    Defines what the baselines mean for Phase 2 ablation based on the current implementation.
    Does NOT execute the ablation.
    """
    return {
        "naive_baseline": "Predict 1 (privacy clause) for every sentence. High recall, terrible precision.",
        "composite_approach": "The current C1 pipeline: TF-IDF + Logistic Regression prefilter -> LLM extraction."
    }
