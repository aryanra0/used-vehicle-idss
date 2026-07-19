"""Multi-source harmonization: blend the three real price datasets into one table.

Sources (all in data/raw/):
- true_car_listings.csv : ~852k retail listings, <=2018, has VIN/City/State
- car_prices.csv        : ~558k wholesale/auction, <=2015, has condition + MMR + saledate
- used_cars.csv         : ~4k retail, 2013-2024, recency coverage

All are mapped to a common schema with a `source_channel` flag so the model can
learn the wholesale-vs-retail price offset instead of averaging it.

Common schema columns:
    price, year, mileage, make, model, state, condition, source_channel, source
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .. import config

COMMON_COLUMNS = [
    "price", "year", "mileage", "make", "model", "state",
    "condition", "source_channel", "source",
]

# Sanity bounds for filtering impossible / outlier rows.
PRICE_MIN, PRICE_MAX = 500.0, 300_000.0
MILEAGE_MIN, MILEAGE_MAX = 10.0, 400_000.0
YEAR_MIN, YEAR_MAX = 1990, 2025


# --- parsing helpers -----------------------------------------------------
def _to_number(series: pd.Series) -> pd.Series:
    """Strip $, commas, ' mi.' etc. and coerce to float."""
    return pd.to_numeric(
        series.astype("string").str.replace(r"[^0-9.]", "", regex=True),
        errors="coerce",
    )


def _norm_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.lower()


_TRANS_SUFFIX = re.compile(
    r"\s*\d?-?\s*(speed|spd)?\s*(a/t|m/t|automatic|manual|cvt|auto)\.?$",
    re.IGNORECASE,
)


def _strip_transmission_from_model(model: pd.Series) -> pd.Series:
    """true_car_listings smushes transmission onto model, e.g. 'ILX6-Speed'."""
    return (
        model.astype("string")
        .str.replace(_TRANS_SUFFIX, "", regex=True)
        .str.strip()
    )


# --- per-source loaders --------------------------------------------------
def load_true_car(path: Optional[Path] = None, nrows: Optional[int] = None) -> pd.DataFrame:
    path = Path(path) if path else config.RAW_DATA_DIR / "true_car_listings.csv"
    df = pd.read_csv(path, nrows=nrows)
    df.columns = [c.strip().lower() for c in df.columns]
    out = pd.DataFrame({
        "price": _to_number(df["price"]),
        "year": pd.to_numeric(df["year"], errors="coerce"),
        "mileage": _to_number(df["mileage"]),
        "make": _norm_text(df["make"]),
        "model": _norm_text(_strip_transmission_from_model(df["model"])),
        "state": _norm_text(df["state"]),
        "condition": np.nan,
        "source_channel": "retail",
        "source": "true_car_listings",
    })
    return out


def load_car_prices(path: Optional[Path] = None, nrows: Optional[int] = None) -> pd.DataFrame:
    path = Path(path) if path else config.PRIMARY_DATASET
    df = pd.read_csv(path, nrows=nrows, on_bad_lines="skip", low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]
    out = pd.DataFrame({
        "price": _to_number(df["sellingprice"]),
        "year": pd.to_numeric(df["year"], errors="coerce"),
        "mileage": _to_number(df["odometer"]),
        "make": _norm_text(df["make"]),
        "model": _norm_text(df["model"]),
        "state": _norm_text(df["state"]),
        "condition": pd.to_numeric(df["condition"], errors="coerce"),
        "source_channel": "wholesale",
        "source": "car_prices",
    })
    return out


def load_used_cars(path: Optional[Path] = None, nrows: Optional[int] = None) -> pd.DataFrame:
    path = Path(path) if path else config.RAW_DATA_DIR / "used_cars.csv"
    df = pd.read_csv(path, nrows=nrows)
    df.columns = [c.strip().lower() for c in df.columns]
    out = pd.DataFrame({
        "price": _to_number(df["price"]),
        "year": pd.to_numeric(df["model_year"], errors="coerce"),
        "mileage": _to_number(df["milage"]),
        "make": _norm_text(df["brand"]),
        "model": _norm_text(df["model"]),
        "state": np.nan,           # no location in this source
        "condition": np.nan,
        "source_channel": "retail",
        "source": "used_cars",
    })
    return out


# --- blend + clean -------------------------------------------------------
def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["price", "year", "mileage", "make", "model"])
    df = df[
        df["price"].between(PRICE_MIN, PRICE_MAX)
        & df["mileage"].between(MILEAGE_MIN, MILEAGE_MAX)
        & df["year"].between(YEAR_MIN, YEAR_MAX)
    ]
    df["year"] = df["year"].astype(int)
    df["state"] = df["state"].fillna("unknown").astype(str)
    # Dedup exact rows across sources.
    df = df.drop_duplicates(subset=["price", "year", "mileage", "make", "model", "state"])
    return df.reset_index(drop=True)


def load_blended(nrows_per_source: Optional[int] = None) -> pd.DataFrame:
    """Load all three sources, harmonize, clean, and concatenate."""
    frames = [
        load_true_car(nrows=nrows_per_source),
        load_car_prices(nrows=nrows_per_source),
        load_used_cars(nrows=nrows_per_source),
    ]
    blended = pd.concat(frames, ignore_index=True)
    return clean(blended)[COMMON_COLUMNS]


def split_recent_holdout(
    df: pd.DataFrame, test_frac: float = 0.2, recent_year: int = 2020, seed: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (train, test, recent_holdout).

    A dedicated recent (>= recent_year) holdout is carved out first so we can
    report honest accuracy on modern cars; the rest is split randomly.
    """
    recent = df[df["year"] >= recent_year]
    older = df[df["year"] < recent_year]
    # Hold out ~40% of recent rows for the recency test; keep the rest for training.
    recent_holdout = recent.sample(frac=0.4, random_state=seed) if len(recent) else recent
    recent_train = recent.drop(recent_holdout.index) if len(recent) else recent

    rest = pd.concat([older, recent_train], ignore_index=False)
    test = rest.sample(frac=test_frac, random_state=seed)
    train = rest.drop(test.index)
    return (
        train.reset_index(drop=True),
        test.reset_index(drop=True),
        recent_holdout.reset_index(drop=True),
    )
