"""Central configuration for the Used Vehicle Acquisition IDSS.

Holds file paths and the default, user-overridable decision thresholds.
Keep constants here so the values referenced in the PRD/spec live in one place.
"""

from __future__ import annotations

from pathlib import Path

# --- Paths ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
MODELS_DIR = PROJECT_ROOT / "models"

# Blended training sources (see idss/data/harmonize.py).
PRIMARY_DATASET = RAW_DATA_DIR / "car_prices.csv"          # wholesale + condition + MMR
TRUE_CAR_DATASET = RAW_DATA_DIR / "true_car_listings.csv"  # retail base
USED_CARS_DATASET = RAW_DATA_DIR / "used_cars.csv"         # recency (2019+)
DTT_BENCHMARK_XLS = RAW_DATA_DIR / "2016-10-dtt.xls"       # days-to-sell benchmark

# --- Default decision thresholds (user-overridable) ----------------------
DEFAULT_TARGET_MARGIN = 0.15      # 15% ROI
DEFAULT_MIN_DOLLAR_PROFIT = 1000  # $1,000 minimum gross profit
DEFAULT_RISK_TOLERANCE = 0.60     # minimum model confidence to recommend Buy

# --- M3 label: profitable at a wholesale acquisition -----------------------
# Dealerships buy below market value (wholesale) and resell higher. M3 predicts
# whether a car, if bought at a typical discount below its market value (MMR),
# would still resell for enough to clear the target margin. This is the real
# acquisition question and is learnable from vehicle features, unlike the
# "beats MMR" framing, which is near-noise (MMR already predicts the sale price).
DEFAULT_ACQUISITION_DISCOUNT = 0.20  # dealer buys ~20% below market value

# --- Days-to-Sell bands (days), calibrated to the benchmark distribution --
# Distribution clusters ~40-105 days (median ~71); cutoffs also map to
# dealer practice (60 = ideal window, 90 = overage warning, 120 = auction).
DTS_BAND_EDGES = [60, 90, 120]  # -> Fast, Moderate, Slow, Very slow
DTS_BAND_LABELS = ["Fast", "Moderate", "Slow", "Very slow"]


def days_to_band(days: float) -> str:
    """Map an average days-to-sell value to its band label."""
    if days <= DTS_BAND_EDGES[0]:
        return DTS_BAND_LABELS[0]
    if days <= DTS_BAND_EDGES[1]:
        return DTS_BAND_LABELS[1]
    if days <= DTS_BAND_EDGES[2]:
        return DTS_BAND_LABELS[2]
    return DTS_BAND_LABELS[3]
