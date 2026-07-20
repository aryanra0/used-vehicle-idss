# Implementation Plan

Status reflects the single-source (`car_prices`) build. Earlier plan items around a
three-source blend (VIN decode, `source_channel`, cross-fold market-value proxy, 2020+
recency holdout) were retired — see `data/README.md` for the rationale.

- [x] 1. Project skeleton and configuration
  - `src/`, `tests/`, `data/`, `models/`; `config.py` for thresholds and paths; default
    assumptions (15% margin, $1,000 min profit, 0.60 confidence, 20% acquisition discount).
  - _Requirements: 4.3_

- [x] 2. Single-source dataset loader, cleaning, and split
  - `src/idss/data/dataset.py`: load `car_prices.csv`; parse numeric strings; sanity-bound
    price/mileage/year; sanitize the contaminated `transmission` column; drop rows missing
    required fields; de-duplicate; random seeded train/val/test split persisted to
    `data/processed/`.
  - _Requirements: 10.1, 10.2, 10.3, 10.6, 12.1, 12.2_

- [x] 3. Days-to-sell benchmark lookup (Edmunds DTT)
  - Parse `2016-10-dtt.xls` (via `xlrd`) into a make -> average-days table; map make to a
    band; label benchmark-level. Unit-tested.
  - _Requirements: 11.1, 11.2, 11.3_

- [x] 4. Market value (real MMR)
  - Use the real `mmr` column as a feature; for user-entered vehicles, a make/model/year
    median lookup with progressive fallback and sample-size tracking; compute the
    price-vs-MMR delta. Unit-tested (exact match + fallback levels).
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 12.3_

- [x] 5. Feature engineering (shared train/serve)
  - Raw UI fields (year, make, model, body, transmission, state, color, mileage, condition)
    + real MMR (`market_value`) + engineered vehicle age and mileage-per-year. No leakage
    (price excluded; MMR permitted). Unit-tested.
  - _Requirements: 3.5, 10.5, 12.4_

- [x] 6. Model training and registry
  - [x] 6.1 M1 resale regression — `HistGradientBoostingRegressor`, log-transformed target.
    - _Requirements: 3.1, 10.4_
  - [x] 6.2 M2 days-to-sell band classifier — `HistGradientBoostingClassifier` on benchmark labels.
    - _Requirements: 3.2, 11.2_
  - [x] 6.3 M3 buy/pass — `HistGradientBoostingClassifier` + `CalibratedClassifierCV` (isotonic),
    threshold tuned on the validation set (calibrated on a capped sample for memory).
    - _Requirements: 3.4, 4.5_
  - [x] 6.4 Versioned model registry (artifact + metadata: metrics, feature list).
    - _Requirements: 3.6_

- [x] 7. Model evaluation and release gate
  - M1 (MAE/MAPE/RMSLE/R2) vs an MMR-quote baseline; M2 (accuracy/macro-F1); M3 (F1 at
    tuned threshold + trivial-baseline F1, ROC-AUC, AUC-PR, calibration); per-state error.
  - _Requirements: 10.7, 10.8, 10.9_

- [x] 8. Decision engine
  - [x] 8.1 Face-value buy/pass (ROI >= margin AND profit >= min AND confidence >= risk tolerance). Boundary-tested.
    - _Requirements: 4.1, 4.4_
  - [x] 8.2 Max-purchase-price formula + financials (gross profit, ROI, holding cost). Tested with the worked $8,500 example.
    - _Requirements: 3.3, 4.2_

- [x] 9. Confidence and data-quality guards
  - Per-prediction confidence (resale/market value/days-to-sell/buy-pass); reconcile a
    low-confidence resale toward MMR; advisory data-quality flags that do not change the
    verdict; verdict-consistent price guidance.
  - _Requirements: 2.4, 3.7, 3.8, 4.7, 4.8_

- [x] 10. Evaluation service (orchestration)
  - Featurize -> MMR + DTT lookups -> M1/M2/M3 -> reconcile -> decision engine -> confidence +
    flags + guidance -> assemble result. Caches per-vehicle outputs; emits an out-of-coverage
    warning for model years beyond 2015.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 5.2, 5.3, 12.5_

- [x] 11. Single-vehicle and CSV batch input paths
  - Single-vehicle manual entry with per-evaluation assumptions; CSV bulk upload with row
    validation, an error report for invalid rows, and selectable ranking.
  - _Requirements: 1.1, 1.2, 1.3, 1.5, 6.1, 6.2, 8.2_

- [x] 12. FastAPI backend
  - `src/idss/api/main.py`: `/evaluate`, `/evaluate-batch`, `/options`, `/metadata`, `/health`.
  - _Requirements: 3.1, 5.2_

- [x] 13. Next.js dashboard
  - Input rail (condition on a 0–100 scale, assumptions), verdict card with confidence,
    price comparison with confidence chips + guidance, financial and risk summaries,
    prediction-confidence card, data-quality banners, top factors, and the batch view.
  - _Requirements: 5.1, 6.1, 6.2, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 14. Tests
  - Unit: config/bands, DTT benchmark, MMR lookup, feature engineering (no leakage), the M3
    wholesale-profit label, and the decision engine. Frontend TypeScript typecheck.
  - _Requirements: 10.x_

- [ ] 15. Monitoring, retraining, and fairness (future)
  - Log predictions with model versions; join realized outcomes; compute drift and per-state
    fairness checks; add rolling-window and degradation retraining triggers. Harden the
    optional live-pricing integration.
  - _Requirements: 9.1, 9.2, 9.3, 9.4_
