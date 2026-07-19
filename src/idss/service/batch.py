"""Bulk CSV evaluation: validate rows, evaluate valid ones, report errors, rank.

Valid rows are evaluated even when some rows are invalid (Requirement 1.3).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .evaluation import EvaluationService
from .types import Assumptions, VehicleInput

REQUIRED_COLUMNS = ["make", "model", "year", "odometer", "condition"]
OPTIONAL_COLUMNS = [
    "trim", "body", "transmission", "state", "color", "interior", "mmr", "listing_price",
]

_RANK_KEYS = {
    "profit": ("expected_gross_profit", True),
    "roi": ("roi", True),
    "risk": ("_risk_rank", False),
}
_RISK_ORDER = {"Low": 0, "Medium": 1, "High": 2}


def _validate_row(row: pd.Series) -> Optional[str]:
    """Return an error message if the row is invalid, else None."""
    for col in REQUIRED_COLUMNS:
        if col not in row or pd.isna(row[col]) or str(row[col]).strip() == "":
            return f"missing required field '{col}'"
    try:
        year = int(row["year"])
        if not (1980 <= year <= 2025):
            return f"year {year} out of range 1980-2025"
        if float(row["odometer"]) < 0:
            return "odometer is negative"
        float(row["condition"])
    except (ValueError, TypeError):
        return "non-numeric year/odometer/condition"
    return None


def _to_vehicle(row: pd.Series) -> VehicleInput:
    def opt(col, default=""):
        val = row.get(col, default)
        return default if pd.isna(val) else val

    def opt_num(col):
        val = row.get(col)
        try:
            return None if pd.isna(val) else float(val)
        except (ValueError, TypeError):
            return None

    return VehicleInput(
        year=int(row["year"]),
        make=str(row["make"]),
        model=str(row["model"]),
        odometer=float(row["odometer"]),
        condition=float(row["condition"]),
        trim=str(opt("trim")),
        body=str(opt("body")),
        transmission=str(opt("transmission")),
        state=str(opt("state")),
        color=str(opt("color")),
        interior=str(opt("interior")),
        mmr=opt_num("mmr"),
        listing_price=opt_num("listing_price"),
    )


def evaluate_csv(
    df: pd.DataFrame,
    service: EvaluationService,
    assumptions: Optional[Assumptions] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate a dataframe of listings. Returns (results, errors)."""
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    results, errors = [], []
    for i, row in df.iterrows():
        err = _validate_row(row)
        if err:
            errors.append({"row": int(i) + 2, "error": err})  # +2: header + 1-index
            continue
        res = service.evaluate(_to_vehicle(row), assumptions)
        results.append(
            {
                "row": int(i) + 2,
                "make": row["make"],
                "model": row["model"],
                "year": int(row["year"]),
                "recommendation": res.recommendation,
                "confidence": res.confidence,
                "predicted_resale": res.predicted_resale_price,
                "max_purchase_price": res.max_purchase_price,
                "expected_gross_profit": res.expected_gross_profit,
                "roi": res.roi,
                "days_to_sell_band": res.days_to_sell_band,
                "risk_level": res.risk_summary.risk_level,
                "_risk_rank": _RISK_ORDER.get(res.risk_summary.risk_level, 1),
            }
        )

    return pd.DataFrame(results), pd.DataFrame(errors)


def rank_results(results: pd.DataFrame, objective: str = "profit") -> pd.DataFrame:
    """Sort evaluated results by an objective: 'profit', 'roi', or 'risk'."""
    if results.empty:
        return results
    key, descending = _RANK_KEYS.get(objective, _RANK_KEYS["profit"])
    ranked = results.sort_values(key, ascending=not descending).reset_index(drop=True)
    return ranked.drop(columns=["_risk_rank"], errors="ignore")
