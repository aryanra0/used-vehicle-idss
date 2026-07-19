"""Per-prediction confidence scoring and data-quality guards.

Each model output (resale price, market value, days-to-sell band, buy/pass) is
paired with a reliability score in [0, 1] and a short human-readable basis, so
the UI can show *how much to trust each number* instead of presenting them all
with equal authority. The same signals feed a set of data-quality flags that
catch outputs which don't add up: an implausible below-market price, a resale
estimate that disagrees with the market benchmark, zero mileage, or a silly ROI.

Pure functions: no I/O, no model calls, so they are cheap and easy to test.
"""

from __future__ import annotations

from typing import Optional

from .types import DataQualityFlag, PredictionConfidence, VehicleInput

# How well the market-value benchmark actually matched the vehicle. A precise
# make/model/year match is trustworthy; a make-only or global fallback is not.
_MATCH_LEVEL_BASE = {
    "provided": 0.90,        # user supplied the MMR directly
    "live": 0.90,            # live market feed
    "make/model/year": 0.85,
    "make/model": 0.60,
    "make": 0.35,
    "global": 0.15,
    "none": 0.10,
}

# Divergence between the ML resale estimate and the market benchmark (MMR).
_DIVERGE_WARN = 0.30
_DIVERGE_BAD = 0.50
# A purchase price this far below market is almost never a real bargain.
_TOO_GOOD_DELTA = -0.60
# ROI above this usually means the inputs are wrong, not that the deal is great.
_IMPLAUSIBLE_ROI = 1.0
# Plausible odometer ceiling before we ask the user to double-check.
_HIGH_MILEAGE = 300_000


def _clip(x: float, lo: float = 0.02, hi: float = 0.98) -> float:
    return max(lo, min(hi, x))


def _level(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.50:
        return "Medium"
    if score >= 0.30:
        return "Low"
    return "Very low"


def _pc(score: float, basis: str) -> PredictionConfidence:
    s = round(_clip(score), 3)
    return PredictionConfidence(score=s, level=_level(s), basis=basis)


# --- per-prediction confidence -------------------------------------------
def market_value_confidence(
    match_level: str, sample_size: Optional[int] = None
) -> PredictionConfidence:
    """Reliability of the market-value (MMR) benchmark."""
    base = _MATCH_LEVEL_BASE.get(match_level, 0.30)
    basis = {
        "provided": "You supplied the market value.",
        "live": "Median of live market listings.",
        "make/model/year": "Median of matching make / model / year sales.",
        "make/model": "Median across all years for this make / model.",
        "make": "Only a make-level median was available (no model match).",
        "global": "No make match; using the overall dataset median.",
        "none": "No comparable sales found.",
    }.get(match_level, f"Matched at '{match_level}'.")

    if sample_size is not None:
        if sample_size < 5:
            base *= 0.55
            basis += f" Only {sample_size} comparable sale(s)."
        elif sample_size < 25:
            base *= 0.80
            basis += f" {sample_size} comparable sales."
        else:
            basis += f" {sample_size:,} comparable sales."
    return _pc(base, basis)


def resale_confidence(
    *,
    price_source: str,
    match_level: str,
    resale: Optional[float],
    mmr: Optional[float],
    coverage_warning: Optional[str],
) -> PredictionConfidence:
    """Reliability of the M1 resale-price prediction."""
    if price_source == "live":
        return _pc(0.88, "Anchored to current live market listings.")

    base = _MATCH_LEVEL_BASE.get(match_level, 0.30)
    reasons: list[str] = []

    if match_level in ("make", "global", "none"):
        reasons.append("few comparable vehicles in the training data")
    if coverage_warning:
        base *= 0.40
        reasons.append("vehicle is outside the model's training coverage")
    if mmr and mmr > 0 and resale is not None:
        div = abs(float(resale) - float(mmr)) / float(mmr)
        if div >= _DIVERGE_BAD:
            base *= 0.40
            reasons.append(f"predicted resale disagrees with market value by {div:.0%}")
        elif div >= _DIVERGE_WARN:
            base *= 0.70
            reasons.append(f"predicted resale differs from market value by {div:.0%}")

    basis = "Gradient-boosted resale model"
    basis += (" — " + "; ".join(reasons) + ".") if reasons else " on a well-represented segment."
    return _pc(base, basis)


def days_band_confidence(
    *, band_proba: Optional[float], from_live_dom: bool = False
) -> PredictionConfidence:
    """Reliability of the M2 days-to-sell band."""
    if from_live_dom:
        return _pc(0.85, "From live median days-on-market.")
    p = 0.5 if band_proba is None else float(band_proba)
    return _pc(p, f"Classifier probability {p:.0%} (make-level benchmark).")


def buy_pass_confidence(profit_p: float, resale_score: float) -> PredictionConfidence:
    """Reliability of the buy/pass call = confidence in the underlying valuation.

    A recommendation is only as trustworthy as its weakest link: the profit
    model's P(good buy) *and* the reliability of the resale estimate the whole
    deal rests on. We take the lower of the two. Data-quality flags (e.g. an
    abnormally low price) are advisory warnings and deliberately do NOT lower
    this — the Buy/Pass call is made on face-value economics.
    """
    effective = min(profit_p, resale_score)
    limiter = "resale estimate" if resale_score < profit_p else "profit model"
    basis = (
        f"Lower of profit-model {profit_p:.0%} and resale reliability "
        f"{resale_score:.0%} (limited by the {limiter})."
    )
    return _pc(effective, basis)


# --- data-quality guards --------------------------------------------------
def collect_flags(
    v: VehicleInput,
    *,
    resale: Optional[float],
    mmr: Optional[float],
    delta: Optional[float],
    roi: Optional[float],
) -> list[DataQualityFlag]:
    """Flag inputs/outputs that don't add up. Order: most severe first."""
    flags: list[DataQualityFlag] = []

    def add(severity: str, message: str) -> None:
        flags.append(DataQualityFlag(severity=severity, message=message))

    # Too-good-to-be-true purchase price (the headline nonsense case).
    if delta is not None and delta <= _TOO_GOOD_DELTA:
        add(
            "alert",
            f"Purchase price is {abs(delta):.0%} below market value. That far below "
            "market almost always means a salvage/branded title, the wrong trim, or a "
            "data-entry error rather than a genuine bargain — verify before buying.",
        )

    # Resale estimate vs market benchmark disagree sharply.
    if mmr and mmr > 0 and resale is not None:
        div = abs(float(resale) - float(mmr)) / float(mmr)
        if div >= _DIVERGE_BAD:
            add(
                "warn",
                f"Predicted resale (${float(resale):,.0f}) and market value "
                f"(${float(mmr):,.0f}) disagree by {div:.0%}; treat the valuation as "
                "low-confidence.",
            )

    # Odometer.
    try:
        odo = float(v.odometer)
    except (TypeError, ValueError):
        odo = None
    if odo is None or odo <= 0:
        add(
            "warn",
            "Mileage is 0 — enter the actual odometer reading. A used-vehicle "
            "valuation with no mileage is unreliable.",
        )
    elif odo > _HIGH_MILEAGE:
        add("warn", f"Mileage {odo:,.0f} is unusually high; confirm it is correct.")

    # Model year.
    try:
        yr = int(v.year)
    except (TypeError, ValueError):
        yr = 0
    if yr <= 0:
        add("warn", "Model year is missing or invalid.")

    # Implausible ROI.
    if roi is not None and roi > _IMPLAUSIBLE_ROI:
        add(
            "warn",
            f"Projected ROI of {roi:.0%} is implausibly high and usually reflects a bad "
            "price or missing inputs rather than a real opportunity.",
        )

    return flags
