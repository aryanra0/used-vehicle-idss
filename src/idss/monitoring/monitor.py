"""Lightweight monitoring: prediction logging and drift / fairness checks.

Prediction logging appends each served evaluation (with model versions) to a
JSONL file so realized outcomes can later be joined for accuracy tracking.
Drift and per-state fairness checks compare a recent batch against training
reference statistics.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .. import config

LOG_PATH = config.PROJECT_ROOT / "logs" / "predictions.jsonl"


def log_prediction(vehicle: dict, result: dict, model_versions: dict,
                   path: Optional[Path] = None) -> None:
    """Append one served prediction to the JSONL prediction log."""
    path = Path(path) if path else LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "vehicle": vehicle,
        "result": result,
        "model_versions": model_versions,
    }
    with path.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def population_stability_index(expected: np.ndarray, actual: np.ndarray,
                               bins: int = 10) -> float:
    """PSI between a reference (expected) and a new (actual) numeric sample.
    PSI < 0.1 = no significant shift; 0.1-0.25 = moderate; > 0.25 = large shift.
    """
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    quantiles = np.linspace(0, 100, bins + 1)
    edges = np.unique(np.percentile(expected, quantiles))
    if len(edges) < 3:
        return 0.0
    e_perc = np.histogram(expected, bins=edges)[0] / max(len(expected), 1)
    a_perc = np.histogram(actual, bins=edges)[0] / max(len(actual), 1)
    eps = 1e-6
    e_perc = np.clip(e_perc, eps, None)
    a_perc = np.clip(a_perc, eps, None)
    return float(np.sum((a_perc - e_perc) * np.log(a_perc / e_perc)))


def per_state_error_gap(errors_by_state: dict, min_states: int = 2) -> Optional[dict]:
    """Given {state: mae}, report the best/worst states and the gap between them."""
    if len(errors_by_state) < min_states:
        return None
    items = sorted(errors_by_state.items(), key=lambda kv: kv[1])
    best_state, best = items[0]
    worst_state, worst = items[-1]
    return {
        "best_state": best_state, "best_mae": best,
        "worst_state": worst_state, "worst_mae": worst,
        "gap": worst - best,
        "gap_ratio": (worst / best) if best > 0 else float("inf"),
    }
