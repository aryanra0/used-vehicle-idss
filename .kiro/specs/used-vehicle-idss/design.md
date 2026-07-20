# Design Document

## Overview
The IDSS is a modular, mostly-offline-trained system with a real-time evaluation path. A user enters a vehicle (or a CSV batch), the system enriches it with a market-value benchmark (MMR) and a make/segment days-to-sell benchmark, runs three models (resale price, days-to-sell band, profitability), applies a rule-based decision engine, and renders results on a dashboard. Models are trained offline on historical sales data; predictions are served in real time.

Design goals: interpretability (separate models for price, timing, and decision), fast evaluation (< 5 s), reproducibility, and honesty about data limitations (per-car days-to-sell is a benchmark, not ground truth).

## Data Strategy Summary
All models are trained on a **single real dataset**, `car_prices.csv`, loaded and cleaned by `src/idss/data/dataset.py`. We use one coherent source rather than blending several.

- **`car_prices.csv` (~558k rows, wholesale auction, model years ~1990–2015):** real sold prices, the only **condition** signal, and a real **MMR** (Manheim Market Report) benchmark. Fields: year, make, model, trim, body, transmission, vin, state, condition, odometer, color, mmr, sellingprice, saledate.
- **Days-to-sell benchmark (`2016-10-dtt.xls`, Edmunds "Days To Turn"):** monthly average days-to-sell by make/segment → M2 band.
- **Present but unused:** `true_car_listings.csv` and `used_cars.csv` remain in `data/raw/` from an earlier three-source blend but are not loaded now; `harmonize.py` (the old multi-source loader) is retained but unused.
- **Rejected:** `car_sales_data.csv` (synthetic), Moroccan dataset (wrong market), `car_sales_demographics.csv` (demographics only).
- **Future:** MarketCheck/Auto.dev live API for truly current prices.

**Why one source (not a blend):** the earlier blend suffered from inconsistent model naming across sources (benchmark lookups missed and fell back to a useless make-level median) and mixed retail-asking vs wholesale-sold prices (making "resale" ambiguous relative to the wholesale MMR). `car_prices` alone gives consistent naming, a real MMR, condition, and one price basis (wholesale) comparable to MMR.

**Documented limitations:**
- **Wholesale basis:** "resale" is a wholesale value (a conservative proxy for retail margin).
- **Rare-vehicle coverage:** exotics/low-volume models have few comparables → lower-confidence estimates that are reconciled toward MMR.
- **Recency:** source is ~1990–2015 (bulk 2014–2015); the out-of-coverage warning triggers beyond model year 2015. Current prices require a live feed.

## Data Pipeline (offline, run before modeling)
`src/idss/data/dataset.py` + `src/idss/train.py`:

1. **Load + clean** `car_prices.csv`: parse `$10,300`→10300 and `51,000 mi.`→51000; drop rows missing price/mmr/year/mileage/make/model; sanity-bound price ($500–$250k), mileage (1–400k), year (1990–2015); lowercase/trim categoricals; sanitize the contaminated `transmission` column (keep only `automatic`/`manual`); de-duplicate.
2. **Split** — random, seeded train / validation / test; the validation set tunes the M3 threshold; persist splits to `data/processed/`.
3. **Feature engineering** — see Component 3.
4. **Target transform + encoding** — log-transform the price target (invert on output); ordinal-encode categoricals for the tree models; standardization only for any linear baseline.

## Technology Choices
- Language: Python 3.9+.
- Data / features: pandas, numpy; `xlrd` to read the legacy `.xls` benchmark.
- Models: scikit-learn `HistGradientBoosting` (regressor for M1, classifier for M2/M3); joblib for artifact persistence. XGBoost/LightGBM are drop-in alternatives; a linear/majority baseline sets the floor.
- Calibration: `CalibratedClassifierCV` (isotonic) for M3; the decision threshold is tuned on the validation set.
- Serving: **FastAPI** (`src/idss/api/main.py`). UI: **Next.js / React** (`web/`).
- Storage: local files for datasets and cached artifacts; a versioned model registry (joblib artifact + JSON metadata sidecar).

Rationale: gradient-boosted trees are the established best performers for tabular used-car price prediction, and scikit-learn's HistGradientBoosting needs no extra system libraries. A FastAPI + Next.js split keeps the model service and the dashboard cleanly decoupled.

## Architecture

```
          +-------------------+
User ---> |  Dashboard (UI)   |  input, sliders, results
          +---------+---------+
                    |
                    v
          +-------------------+     +--------------------------+
          | Evaluation Service| <-> | Benchmark Lookups        |
          | (orchestration)   |     | MMR + make/segment DTT   |
          +----+----+----+----+     +--------------------------+
               |    |    |
               v    v    v
        +------+ +--------+ +----------+
        | M1   | | M2     | | M3       |   trained model artifacts
        |resale| |DTS band| |buy/pass  |
        +------+ +--------+ +----------+
               |    |    |
               v    v    v
          +-------------------+
          |  Decision Engine  |  buy/pass + max price (rules)
          +-------------------+

Offline: Load car_prices -> Clean (parse/bound/sanitize/dedup) -> Split (train/val/test) ->
         Feature Engineering (real MMR + age + miles/yr) -> Transform/Encode ->
         Train/Eval (MAE/R2 vs MMR baseline; M3 threshold on val) -> Model Registry
Monitoring: realized outcomes -> metrics compare -> drift/fairness checks -> retrain trigger
```

## Components and Interfaces

### 1. Data Ingestion and Cleaning
- Loads the single source (`car_prices.csv`) into the cleaned schema.
- Responsibilities: parse price/mileage strings; normalize categorical casing and state codes; sanitize the contaminated `transmission` column; filter price/mileage/year outliers; de-duplicate.
- Output: a cleaned table split into train / validation / test (persisted to `data/processed/`).

### 2. Benchmark Lookup (MMR + Days-to-Sell)
- **MMR:** the real `mmr` column per record at training time. For a user-entered vehicle: prefer a user-provided MMR, then a live feed (if configured), else a make/model/year median from the training data with progressive fallback (make/model/year → make/model → make → global) and sample-size tracking. Interface: `MmrLookup.lookup_detailed(make, model, year) -> (value, match_level, sample_size)`.
- **Days-to-Sell benchmark:** parse the Edmunds `.xls` into a make -> average-days table; map each vehicle's make to a benchmark and then to a band. Interface: `DtsBenchmark.band_for(make) -> band`.

### 3. Feature Engineering (shared train/serve)
- Raw: year, make, model, body, transmission, state, color, mileage, condition — only fields the UI collects, so every input the user changes moves the prediction.
- **Real MMR** (`market_value`): the vehicle's Manheim MMR, an external pre-sale benchmark (not the sale price → no leakage) and the strongest single feature.
- Engineered: vehicle age (reference year 2016 − model year); mileage-per-year.
- Constraint: only pre-acquisition features (no leakage — the sale `price` is the sole excluded column). Shared by training and serving to avoid train/serve skew. `condition` may be NaN (tree models handle natively).

### 4. Model Layer (M1, M2, M3)
- **M1 Resale Price (regression):** target = wholesale sale price, trained on the single source with the real MMR as a feature. Log-transform the skewed target and invert on output; report error on the dollar scale against an MMR-quote baseline. Primary: `HistGradientBoostingRegressor` (XGBoost/LightGBM optional); baseline: linear regression.
- **M2 Days-to-Sell Band (multi-class classification):** predicts a sale-time band in days — Fast (<=60), Moderate (61-90), Slow (91-120), Very slow (>120) — calibrated to the observed benchmark distribution (~40-105 days, median ~71). Labels derived from the make benchmark join. `HistGradientBoostingClassifier`; baseline: majority class. Presented as a band and labeled benchmark-level.
- **M3 Profitability / Buy-Pass (binary classification):** predicts whether a vehicle, if bought at a wholesale discount below MMR (default 20%), would resell for enough to clear the target margin. `HistGradientBoostingClassifier` with `class_weight="balanced"`, wrapped in `CalibratedClassifierCV` (isotonic) for calibrated confidence; the threshold is tuned on the validation set to maximize F1 (calibration runs on a capped sample for memory). Reported with F1, the trivial-baseline F1, ROC-AUC, and AUC-PR. Wholesale-level estimate (a conservative proxy for retail margin).
- Each model is a versioned artifact in a simple Model Registry (path + metadata: version, metrics, feature list).

### 5. Decision Engine (rule-based)
- Inputs: M1/M2/M3 outputs, user assumptions, thresholds.
- **Face-value Buy/Pass:** Buy if ROI >= target margin AND gross profit >= min profit AND confidence >= risk tolerance; else Pass. The verdict is based on the economics only — data-quality flags are advisory and do not override it.
- Max purchase price (a ceiling, not a target): `resale - repairs - (holdingCostPerDay * predictedDaysToSell) - (targetMargin * resale)`.
- Pure function of its inputs (supports reproducibility and fast recompute on slider changes).

### 6. Evaluation Service + Confidence (orchestration)
- Coordinates: featurize -> benchmark lookups -> run models -> reconcile resale toward MMR when low-confidence -> run decision engine -> score confidence + collect data-quality flags + build price guidance -> assemble result.
- **Per-prediction confidence** (`src/idss/service/confidence.py`): scores resale, market value, days-to-sell, and buy/pass each with a value/level/basis. Buy/pass confidence = the weaker of the profit-model probability and the resale reliability, and is the value fed to the risk-tolerance gate.
- **Reconciliation:** a low-confidence resale estimate is blended toward MMR in proportion to confidence (a shrink, not a hard cap).
- **Advisory flags:** abnormally low price, implausible ROI, resale-vs-MMR divergence, and zero mileage are surfaced without changing the verdict.
- **Price guidance:** a plain-language line consistent with the verdict (pay the listing vs. negotiate below the ceiling vs. hold off).
- Caches per-vehicle model outputs so assumption changes only re-run the decision engine (< 1 s recompute).

### 7. Dashboard (UI)
- Views: input form / CSV upload; assumption sliders (margin, holding cost, risk tolerance, holding period); Vehicle Summary card; Price Comparison view (listing vs. max purchase vs. resale vs. MMR); Financial Summary; Risk Summary (days-to-sell band + demand + risk level); inventory comparison table with ranking; top-factor display (feature contributions).

### 8. Monitoring and Retraining
- Logs predictions with model versions; joins realized outcomes when available.
- Computes model + business metrics; runs drift and per-state fairness checks; triggers retraining on a rolling window or on degradation.

## Data Models

### Cleaned Training Schema (per row, from car_prices)
- price: float (target); mmr: float (real MMR benchmark)
- year: int; make: str; model: str; body: str; transmission: str; state: str; color: str
- mileage: int; condition: float (may be NaN)

### VehicleInput (serving)
- year: int
- make: str
- model: str
- body: str (optional)
- transmission: str (optional)
- odometer: int
- condition: float (model's native 1-49 grade; the UI collects a 0-100 score and converts)
- color: str (optional)
- state: str
- mmr: float (optional; a make/model/year median lookup is used if absent)
- listing_price: float (optional)

### Assumptions
- target_profit_margin: float (default 0.15)
- acquisition_discount: float (default 0.20) — wholesale discount used when no listing price is given
- min_dollar_profit: float (default 1000)
- risk_tolerance: float (default 0.60)
- holding_cost_per_day: float
- holding_period_days: int
- repair_estimate: float

### PredictionConfidence
- score: float [0,1]; level: {High, Medium, Low, Very low}; basis: str

### DataQualityFlag
- severity: {alert, warn, info}; message: str

### EvaluationResult
- recommendation: enum {Buy, Pass}
- confidence: float [0,1]
- predicted_resale_price: float
- days_to_sell_band: enum {Fast <=60d, Moderate 61-90d, Slow 91-120d, VerySlow >120d}
- expected_gross_profit: float
- roi: float
- max_purchase_price: float
- market_value_mmr: float | null
- price_vs_mmr_delta: float | null
- resale_confidence / market_value_confidence / days_band_confidence / buy_pass_confidence: PredictionConfidence | null
- data_quality_flags: list[DataQualityFlag]
- price_guidance: str | null
- price_source: {model, live}; coverage_warning: str | null
- financial_summary: object; risk_summary: object; top_factors: list

## Error Handling
- Input validation: reject malformed single entries with field-level messages; for CSV, skip invalid rows and emit an error report.
- Missing MMR benchmark: still produce a recommendation; flag the missing benchmark in the result.
- Missing optional fields: impute with a documented strategy.
- Model/artifact load failure: fail closed with a clear error rather than serving an untracked model.

## Testing Strategy
- Unit tests: config and band mapping, DTT benchmark parsing and band mapping, MMR lookup (exact match + fallback levels), feature engineering (correct values, no leakage, MMR is a legitimate feature), the M3 wholesale-profit label, and the decision engine (buy/pass boundaries, max-price formula incl. the worked $8,500 example).
- Model evaluation: train/validation/test split; M1 (MAE/MAPE/RMSLE/R2 after inverting the log target) against an MMR-quote baseline; M2 (accuracy/macro-F1); M3 (F1 at the tuned threshold + trivial-baseline F1, ROC-AUC, AUC-PR, calibration); per-state error breakdown; gate release on beating the baseline.
- Integration: end-to-end single-vehicle and CSV batch evaluation; missing-MMR fallback path; out-of-coverage (post-2015) warning; confidence/flags/price-guidance consistency with the verdict; assumption-change recompute latency.
- Frontend: TypeScript typecheck (`tsc --noEmit`) over the Next.js app.

## Key Reference
Design of M2 (sale-time as classification into bands) and the choice of tree-based models follow Ahaggach, H., Abrouk, L., Foufou, S., & Lebon, E. (2022), *Predicting Car Sale Time with Data Analytics and Machine Learning*, PLM 2022, pp. 399–409, DOI: 10.1007/978-3-031-25182-5_39.
