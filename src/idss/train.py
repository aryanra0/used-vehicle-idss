"""Train and evaluate the three models on a SINGLE source: car_prices.csv.

car_prices is the only source with a real MMR benchmark and condition grade, it
uses consistent model naming, and it is entirely wholesale, so the resale target
and MMR are comparable. Run from src/ (or with PYTHONPATH=src):

    python -m idss.train                # full dataset
    python -m idss.train --sample 20000 # cap rows (fast dev loop)
"""

from __future__ import annotations

import argparse
import gc
import json

import numpy as np
import pandas as pd

from . import config
from .data import dataset
from .data.dtt_benchmark import load_benchmark
from .data.mmr_lookup import MmrLookup
from .models import evaluate, registry
from .models.dts_band import DaysToSellBandModel, make_band_labels
from .models.profitability import ProfitabilityModel, make_profit_labels
from .models.resale import ResalePriceModel


def _attach_mmr_feature(*frames: pd.DataFrame) -> None:
    """Expose the real MMR column to the models as the `market_value` feature."""
    for df in frames:
        df["market_value"] = df["mmr"]


def _options_from(df: pd.DataFrame) -> dict:
    """Build UI dropdown options from the dataset so picks match the lookup."""
    def top(col, n):
        return sorted(df[col].value_counts().head(n).index.tolist())

    models_by_make = {}
    for mk, g in df.groupby("make"):
        models_by_make[mk] = sorted(g["model"].value_counts().head(40).index.tolist())
    return {
        "makes": sorted(df["make"].value_counts().head(60).index.tolist()),
        "models_by_make": models_by_make,
        "bodies": [b for b in top("body", 30) if b and b != "unknown"],
        "transmissions": ["automatic", "manual"],
        "colors": [c for c in top("color", 25) if c and c != "unknown"],
        "states": [s for s in top("state", 60) if s and s != "unknown"],
        "year_min": int(df["year"].min()),
        "year_max": int(df["year"].max()),
        "condition_min": 1.0,
        "condition_max": 49.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the IDSS models (car_prices only).")
    parser.add_argument("--sample", type=int, default=None,
                        help="Cap rows loaded before cleaning (faster dev loop).")
    args = parser.parse_args()

    print("Loading car_prices.csv ...")
    df = dataset.load_car_prices(nrows=args.sample)
    options = _options_from(df)  # capture before freeing df
    train_df, val_df, test_df = dataset.train_val_test_split(df)
    _attach_mmr_feature(train_df, val_df, test_df)
    out_dir = dataset.persist_splits(train_df, val_df, test_df)
    n_rows = len(df)
    print(f"  rows={n_rows:,}  train={len(train_df):,}  val={len(val_df):,}  "
          f"test={len(test_df):,}  -> splits in {out_dir}")
    del df
    gc.collect()  # free the full frame before the memory-heavy model training

    benchmark = load_benchmark()
    mmr_lookup = MmrLookup(train_df)  # real MMR medians by make/model/year
    margin = config.DEFAULT_TARGET_MARGIN
    discount = config.DEFAULT_ACQUISITION_DISCOUNT
    summary: dict = {}

    # --- M1 resale price -------------------------------------------------
    print("Training M1 (resale price) ...")
    m1 = ResalePriceModel().fit(train_df)
    pred = m1.predict(test_df)
    m1_metrics = evaluate.regression_metrics(test_df["price"], pred)
    # Honest baseline: just quote MMR as the resale. M1 must beat it by using
    # condition / mileage / etc.
    base_mae = float(np.mean(np.abs(test_df["price"].values - test_df["mmr"].values)))
    m1_metrics["mmr_baseline_mae"] = base_mae
    m1_metrics["beats_mmr_baseline"] = evaluate.gate_m1(m1_metrics["mae"], base_mae)
    m1_metrics["per_state_mae_top"] = dict(
        list(evaluate.per_state_mae(
            test_df.rename(columns={"price": "sellingprice"}), pred).items())[:5]
    )
    summary["M1_resale"] = m1_metrics
    print(f"  M1 MAE=${m1_metrics['mae']:,.0f}  MAPE={m1_metrics['mape']:.1%}  "
          f"R2={m1_metrics['r2']:.3f}  MMR-baseline MAE=${base_mae:,.0f}  "
          f"beats={m1_metrics['beats_mmr_baseline']}")

    # --- M2 days-to-sell band -------------------------------------------
    print("Training M2 (days-to-sell band) ...")
    m2 = DaysToSellBandModel().fit(train_df, benchmark)
    m2_pred = m2.predict(test_df)
    m2_metrics = evaluate.classification_metrics(make_band_labels(test_df, benchmark), m2_pred)
    summary["M2_dts_band"] = m2_metrics
    print(f"  M2 accuracy={m2_metrics['accuracy']:.3f}  macro_f1={m2_metrics['macro_f1']:.3f}")

    # Cap the calibration set, then FREE the full training frame: M1/M2 are done
    # with it, and CalibratedClassifierCV(cv=3) is memory-heavy, so keeping 368k
    # rows resident alongside it is what pushes the process over the limit.
    n_train = len(train_df)
    m3_train = train_df.sample(n=min(n_train, 60_000), random_state=42).copy()
    del train_df
    gc.collect()

    # --- M3 buy/pass -----------------------------------------------------
    print("Training M3 (buy/pass) ...")
    m3 = ProfitabilityModel().fit(m3_train, discount, margin)
    m3.choose_threshold(val_df, discount, margin)
    m3_proba = m3.predict_proba(test_df)
    m3_true = make_profit_labels(test_df, discount, margin)
    m3_metrics = evaluate.binary_metrics(m3_true, m3_proba, threshold=m3.threshold)
    summary["M3_buy_pass"] = m3_metrics
    del m3_train
    gc.collect()
    print(f"  M3 F1={m3_metrics['f1']:.3f} (thr={m3_metrics['threshold']:.2f}, "
          f"trivial={m3_metrics['trivial_f1_baseline']:.3f})  AUC={m3_metrics['roc_auc']:.3f}")

    # --- persist ---------------------------------------------------------
    print("Saving models + lookups ...")
    meta = {
        "source": "car_prices",
        "rows_train": int(n_train),
        "rows_val": int(len(val_df)),
        "rows_test": int(len(test_df)),
    }
    registry.save_model("m1_resale", m1, {"metrics": m1_metrics, **meta})
    registry.save_model("m2_dts_band", m2, {"metrics": m2_metrics, **meta})
    registry.save_model("m3_buy_pass", m3, {"metrics": m3_metrics,
                        "acquisition_discount": discount, "target_margin": margin,
                        "threshold": m3.threshold, **meta})
    registry.save_model("mmr_lookup", mmr_lookup, {"proxy": False, **meta})
    registry.save_model("dts_benchmark", benchmark, {"makes": len(benchmark.as_dict())})

    (config.MODELS_DIR / "training_summary.json").write_text(
        json.dumps(summary, indent=2, default=str))
    (config.MODELS_DIR / "options.json").write_text(json.dumps(options))
    print(f"Done. Summary -> {config.MODELS_DIR / 'training_summary.json'}")


if __name__ == "__main__":
    main()
