# Design Document

## Overview
The IDSS is a modular, mostly-offline-trained system with a real-time evaluation path. A user enters a vehicle (or a CSV batch), the system enriches it with a market-value benchmark (MMR) and a make/segment days-to-sell benchmark, runs three models (resale price, days-to-sell band, profitability), applies a rule-based decision engine, and renders results on a dashboard. Models are trained offline on historical sales data; predictions are served in real time.

Design goals: interpretability (separate models for price, timing, and decision), fast evaluation (< 5 s), reproducibility, and honesty about data limitations (per-car days-to-sell is a benchmark, not ground truth).

## Data Strategy Summary
Price models are trained on a **blend of three real datasets**, harmonized to a common schema with a `source_channel` flag. Gradient-boosted trees handle features present in only some sources via native NaN support, so no source-specific column is discarded.

- **`true_car_listings.csv` (~852k rows, retail listings, model years ≤2018):** Price, Year, Mileage, City, State, VIN, Make, Model. Largest, cleanest real source; VINs enable decoding. Primary base for M1.
- **`car_prices.csv` (~558k rows, wholesale auction, ≤2015):** adds real sold prices, **condition**, and **MMR**. Contributes the only condition signal and a real market-value benchmark.
- **`used_cars.csv` (~4k rows, retail, 2013–2024):** small but reaches 2024; contributes recent (2019+) coverage plus fuel/transmission/accident/title.
- **Days-to-sell benchmark (`2016-10-dtt.xls`, Edmunds "Days To Turn"):** monthly average days-to-sell by make/segment → M2 band.
- **Rejected:** `car_sales_data.csv` (+ duplicate) and other synthetic files — randomized make/model, no real price signal; excluded. Moroccan dataset — wrong market/currency.
- **Future:** MarketCheck/Auto.dev live API for truly current prices; `Car Sales.xlsx` (buyer demographics) for demand analysis.

**Known scope costs of the blend (documented limitations):**
- **Condition** exists only for the `car_prices` rows (NaN elsewhere).
- Prices mix **wholesale sold** and **retail asking** — the `source_channel` flag lets the model separate them; the tool reports a configured channel (retail default).
- **MMR** is real only for `car_prices`; elsewhere a **group-median-price proxy** is used and labeled as derived.
- **Recency** is still limited (most rows ≤2018; ~1,258 rows are 2020+), so 2020+ predictions are supported but lower-confidence. Coverage/OOD warning threshold moves to model year 2024.

## Data Pipeline (offline, run before modeling)
A dedicated, ordered pipeline runs before any training:

1. **EDA & profiling** — per source: row counts, dtypes, memory, value ranges, target skew (confirm log transform), missingness, outliers, categorical cardinality, duplicate/overlap scan, and the wholesale-vs-retail price gap. Persists an EDA summary artifact.
2. **Schema harmonization** — map every source to the common schema; record originating source; add `source_channel`.
3. **Parsing/normalization** — `$10,300`→10300, `51,000 mi.`→51000; split transmission out of the model string (e.g., "ILX6-Speed"); lowercase/trim categoricals; standardize state codes.
4. **Dedup** — by VIN where present, else exact-row match, within and across sources.
5. **Outlier/sanity filtering** — documented bounds for price, mileage, year.
6. **Missing-value policy** — per-column; keep source-only columns as NaN for other sources (trees handle natively).
7. **Feature engineering** — see Component 3.
8. **Target transform + encoding** — log-transform price target; ordinal encoding for trees; cross-fold target/frequency encoding for high-cardinality `model` and the group-median market-value proxy (no leakage); standardization only for linear baselines.
9. **Splitting** — chronological by sale date where dates exist, else stratified by year/source; reserve a **recent (2020+) holdout** for a dedicated recency test.

## Technology Choices
- Language: Python 3.11+.
- Data / features: pandas, numpy; `xlrd` to read the legacy `.xls` benchmark.
- Models: scikit-learn baselines and RandomForest; gradient-boosted trees via XGBoost or LightGBM as primary candidates for M1.
- Calibration: scikit-learn probability calibration for M3 (e.g., isotonic or Platt).
- Serving/UI: Streamlit for the MVP dashboard. A FastAPI service is an optional later split.
- Storage: local files/Parquet for datasets, benchmarks, and cached artifacts; a lightweight log (SQLite or Parquet) for prediction/version records.

Rationale: gradient-boosted trees are the established best performers for tabular used-car price prediction; Random Forest is a strong, interpretable alternative and performed best in the referenced sale-time study. Streamlit keeps the MVP simple for a course project.

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

Offline: EDA -> Harmonize 3 sources (+source_channel) -> Parse/Normalize -> Dedup -> Outlier filter ->
         Feature Engineering (+VIN decode, +market-value proxy) -> Transform/Encode -> Split (recent holdout) ->
         Train/Eval (per-source + 2020+ metrics) -> Model Registry
Monitoring: realized outcomes -> metrics compare -> drift/fairness checks -> retrain trigger
```

## Components and Interfaces

### 1. Data Ingestion, Harmonization, and Cleaning
- Loads all three sources; maps each to the common schema and tags `source_channel`.
- Responsibilities: EDA/profiling; parse price/mileage strings; split transmission from the model string; normalize categorical casing and state codes; dedup (VIN + exact-row); filter price/mileage/year outliers; apply the per-column missing-value policy; chronological ordering where sale dates exist.
- Output: a single cleaned, versioned, multi-source training table plus a persisted EDA summary.

### 2. Benchmark Lookup (MMR + Days-to-Sell)
- **MMR:** taken from the primary dataset per record; for a new user-entered vehicle, look up a comparable MMR (by make/model/year/condition) or accept a user-provided value. Interface: `get_market_value(vehicle) -> float | None`.
- **Days-to-Sell benchmark:** parse the Edmunds `.xls` into a make/segment -> average-days table; map each vehicle's make (and segment where derivable) to a benchmark and then to a band. Interface: `get_dts_benchmark(vehicle) -> DtsBand`.

### 3. Feature Engineering (shared train/serve)
- Raw / harmonized: year, make, model, mileage, state, condition (where present), `source_channel`.
- **VIN-decoded** (where a VIN exists): body, cylinders, fuel type, drivetrain — recovers fields the retail source lacks.
- Engineered: vehicle age; mileage-per-year; regional (state) price index; model-frequency / brand tier; **group-median market-value proxy** (make/model/year) computed with cross-fold encoding to avoid target leakage; sale-month seasonal flag where dates exist.
- Constraint: only pre-acquisition features (no leakage). Shared by training and serving to avoid train/serve skew. Features present in only some sources are left NaN elsewhere (tree models handle natively).

### 4. Model Layer (M1, M2, M3)
- **M1 Resale Price (regression):** target = price, trained on the blended multi-source table with a `source_channel` feature so the model learns the wholesale-vs-retail offset; served for a configured channel (retail default). Apply a log transform to the skewed target and invert on output; report error on the dollar scale, **broken down per source and on the 2020+ holdout**. Primary: gradient-boosted trees (HistGradientBoosting; XGBoost/LightGBM optional); baseline: linear regression.
- **M2 Days-to-Sell Band (multi-class classification):** predicts a sale-time band in days — Fast (<=60), Moderate (61-90), Slow (91-120), Very slow (>120) — calibrated to the observed benchmark distribution (values cluster ~40-105 days, median ~71) and dealer overage practice. Labels derived from the make/segment benchmark join. Primary: RandomForest/gradient boosting; baseline: majority class. Output is presented as a band and labeled benchmark-level.
- **M3 Profitability / Buy-Pass (binary classification):** predicts whether a vehicle, if bought at a wholesale discount below market value (MMR, default 20%), would resell for enough to clear the target margin. Uses `HistGradientBoostingClassifier` with `class_weight="balanced"`, wrapped in `CalibratedClassifierCV` (isotonic) for calibrated confidence; the decision threshold is tuned on a validation set to maximize F1. Reported with F1, the trivial-baseline F1, ROC-AUC, and AUC-PR. Note: since the dataset is wholesale/auction data, this estimates profitability at the wholesale level (a conservative proxy for retail margin).
- Each model is a versioned artifact in a simple Model Registry (path + metadata: version, train window, metrics, feature list).

### 5. Decision Engine (rule-based)
- Inputs: M1/M2/M3 outputs, user assumptions, thresholds.
- Buy/Pass: Buy if ROI >= target margin AND gross profit >= min profit AND confidence >= risk tolerance; else Pass.
- Max purchase price: `resale - repairs - (holdingCostPerDay * predictedDaysToSell) - (targetMargin * resale)`.
- Pure function of its inputs (supports reproducibility and fast recompute on slider changes).

### 6. Evaluation Service (orchestration)
- Coordinates: featurize -> benchmark lookups -> run models -> run decision engine -> assemble result.
- Caches per-vehicle model outputs so assumption changes only re-run the decision engine (< 1 s recompute).

### 7. Dashboard (UI)
- Views: input form / CSV upload; assumption sliders (margin, holding cost, risk tolerance, holding period); Vehicle Summary card; Price Comparison view (listing vs. max purchase vs. resale vs. MMR); Financial Summary; Risk Summary (days-to-sell band + demand + risk level); inventory comparison table with ranking; top-factor display (feature contributions).

### 8. Monitoring and Retraining
- Logs predictions with model versions; joins realized outcomes when available.
- Computes model + business metrics; runs drift and per-state fairness checks; triggers retraining on a rolling window or on degradation.

## Data Models

### Harmonized Training Schema (per row)
- price: float (target); source_channel: enum {wholesale, retail}
- year: int; make: str; model: str; mileage: int; state: str
- vin: str (optional); condition: float (optional, present for wholesale source)
- source: str (originating dataset)

### VehicleInput (serving)
- year: int
- make: str
- model: str
- trim: str (optional)
- body: str (optional; VIN-decoded/normalized)
- transmission: str (optional)
- odometer: int
- condition: float (optional; may be unknown)
- color: str (optional)
- state: str
- mmr: float (optional; real MMR or engineered proxy if absent)

### Assumptions
- target_profit_margin: float (default 0.15)
- min_dollar_profit: float (default 1000)
- risk_tolerance: float (default 0.60)
- holding_cost_per_day: float
- holding_period_days: int
- repair_estimate: float

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
- financial_summary: object
- risk_summary: object
- top_factors: list

## Error Handling
- Input validation: reject malformed single entries with field-level messages; for CSV, skip invalid rows and emit an error report.
- Missing MMR benchmark: still produce a recommendation; flag the missing benchmark in the result.
- Missing optional fields: impute with a documented strategy.
- Model/artifact load failure: fail closed with a clear error rather than serving an untracked model.

## Testing Strategy
- Unit tests: data harmonization (schema mapping, `source_channel` tagging), parsers (price/mileage strings, transmission-from-model split, state-code normalization), dedup (VIN + exact row), outlier filtering, feature engineering (correct values, no leakage, cross-fold market-value proxy), decision engine (buy/pass boundaries, max-price formula incl. the worked $8,500 example), CSV validation and error reporting, DTT benchmark parsing and band mapping.
- Model evaluation: split chronologically by sale date where available, else stratified by year/source; M1 (MAE/MAPE/RMSLE/R2 after inverting the log target) reported **overall, per source, and on the 2020+ holdout**; M2 (accuracy/macro-F1/ROC-AUC); M3 (F1 at tuned threshold + trivial-baseline F1, ROC-AUC, AUC-PR, calibration); per-state error breakdown; compare against baselines and gate release.
- Combination check: verify the blended model beats any single source on the 2020+ holdout (Requirement 12.5); if not, reconsider the blend.
- Integration tests: end-to-end single-vehicle and CSV batch evaluation; missing-benchmark/proxy path; out-of-coverage (post-2024) warning; assumption-change recompute latency.
- Backtesting: simulate decisions on held-out recent data and evaluate realized profit vs. model recommendations.

## Key Reference
Design of M2 (sale-time as classification into bands) and the choice of tree-based models follow Ahaggach, H., Abrouk, L., Foufou, S., & Lebon, E. (2022), *Predicting Car Sale Time with Data Analytics and Machine Learning*, PLM 2022, pp. 399–409, DOI: 10.1007/978-3-031-25182-5_39.
