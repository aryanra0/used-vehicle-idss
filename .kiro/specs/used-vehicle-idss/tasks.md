# Implementation Plan

- [ ] 1. Set up project skeleton and configuration
  - Create Python project structure (src/, tests/, data/, models/), dependency management (pandas, numpy, scikit-learn, xgboost/lightgbm, xlrd, streamlit), and a config module for thresholds and paths.
  - Add default assumption values (15% margin, $1,000 min profit, 0.60 confidence) as configurable constants.
  - _Requirements: 4.3_

- [ ] 2. Run EDA and profiling on each source (before modeling)
  - Profile each source (true_car_listings, car_prices, used_cars): rows, dtypes, memory, value ranges, target skew, missingness, outliers, categorical cardinality, duplicate/overlap scan.
  - Quantify the wholesale-vs-retail price gap and the 2020+ row count; persist an EDA summary artifact (e.g., docs/eda_summary.md or JSON).
  - _Requirements: 10.1_

- [ ] 3. Build multi-source ingestion, harmonization, and cleaning
  - [ ] 3.1 Map each source to the common schema (price, year, mileage, make, model, state, vin, condition, source_channel) and tag the originating source.
    - Unit test the per-source column mapping and source_channel tagging.
    - _Requirements: 12.1, 12.2, 12.3_
  - [ ] 3.2 Implement parsers/normalizers: `$`/comma price -> number, "51,000 mi." -> number, split transmission out of the model string, lowercase/trim categoricals, standardize state codes.
    - Unit test each parser.
    - _Requirements: 10.2_
  - [ ] 3.3 Deduplicate within and across sources (by VIN where present, else exact-row match).
    - _Requirements: 10.3_
  - [ ] 3.4 Filter price/mileage/year outliers with documented bounds; apply the per-column missing-value policy (keep source-only columns as NaN for tree models).
    - Test outlier filtering and the missing-value policy.
    - _Requirements: 10.4, 10.5_
  - [ ] 3.5 Split: chronological by sale date where dates exist, else stratified by year/source; reserve a recent (2020+) holdout.
    - _Requirements: 10.8, 12.4_

- [ ] 4. Implement the days-to-sell benchmark lookup (Edmunds DTT)
  - Parse 2016-10-dtt.xls (via xlrd) into a make/segment -> average-days table.
  - Map each vehicle to a benchmark and convert to a sale-time band; label the output benchmark-level.
  - Unit test the parser and the make/segment -> band mapping.
  - _Requirements: 11.1, 11.2, 11.3_

- [ ] 5. Implement the market-value benchmark (real MMR + engineered proxy)
  - Use real MMR where available (car_prices rows); elsewhere compute a group-median-price proxy by make/model/year and label it as derived.
  - Compute the price-vs-benchmark delta for display; handle the missing-benchmark case by flagging it.
  - Ensure any proxy used as a model feature is computed with cross-fold encoding (no leakage).
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 6. Implement feature engineering (shared train/serve)
  - Implement engineered features: vehicle age, mileage-per-year, regional (state) price index, model-frequency/brand tier, cross-fold group-median market-value proxy, `source_channel`, sale-month flag (where dates exist).
  - Implement VIN decoding (where a VIN exists) to recover body/cylinders/fuel/drivetrain.
  - Enforce no-leakage: exclude any feature not knowable before acquisition (incl. the raw price target); add tests asserting excluded fields and that source-only features are left NaN elsewhere.
  - _Requirements: 3.5, 10.7, 12.3_

- [ ] 7. Build model training and registry
  - [ ] 7.1 Implement baselines (linear regression for M1 with standardized numerics, majority-class for M2, logistic regression for M3).
    - _Requirements: 10.7, 10.11_
  - [ ] 7.2 Implement M1 resale-price regression on the blended table with a `source_channel` feature and a log-transformed target (invert on output); serve a configured channel (retail default).
    - _Requirements: 3.1, 10.6, 12.2_
  - [ ] 7.3 Implement M2 days-to-sell band classifier (gradient boosting) on the benchmark-derived labels.
    - _Requirements: 3.2, 11.2_
  - [ ] 7.4 Implement M3 buy/pass classifier and calibrate its probabilities to a confidence in [0,1].
    - _Requirements: 3.4, 4.5_
  - [ ] 7.5 Implement a versioned model registry (artifact + metadata: version, train window, sources, metrics, feature list).
    - _Requirements: 3.6_

- [ ] 8. Implement model evaluation, combination check, and release gate
  - Compute M1 (MAE/MAPE/RMSLE/R2 after inverting the log target) overall, per source, and on the 2020+ holdout; M2 (accuracy/macro-F1/ROC-AUC); M3 (F1 at tuned threshold + trivial-baseline F1, ROC-AUC, AUC-PR, calibration).
  - Verify the blended model beats any single source on the 2020+ holdout; document the result.
  - Compute per-state error breakdown; block release if a model does not beat its baseline by the required margin.
  - _Requirements: 10.9, 10.10, 10.11, 12.5, 9.4_

- [ ] 9. Implement the decision engine
  - [ ] 9.1 Implement buy/pass rule (ROI >= margin AND profit >= min AND confidence >= risk tolerance).
    - Unit test boundary conditions and cost-sensitive bias.
    - _Requirements: 4.1, 4.4_
  - [ ] 9.2 Implement max purchase price formula and financial computations (gross profit, ROI, holding cost).
    - Unit test using the worked example (resale $12,000, repairs $800, 45 days @ $20, 15% -> $8,500 max).
    - _Requirements: 3.3, 4.2_

- [ ] 10. Implement the evaluation service (orchestration)
  - Wire featurize -> benchmark lookups (market value + DTT) -> run M1/M2/M3 -> decision engine -> assemble EvaluationResult.
  - Cache per-vehicle model outputs so assumption changes only re-run the decision engine.
  - Emit an out-of-coverage warning for model years beyond 2024.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 5.2, 5.3_

- [ ] 11. Implement single-vehicle and CSV batch input paths
  - [ ] 11.1 Single-vehicle manual entry with per-evaluation assumptions.
    - _Requirements: 1.1, 1.5_
  - [ ] 11.2 CSV bulk upload: validate rows, process valid rows, and produce a downloadable error report for invalid rows; support >= 1,000 rows.
    - _Requirements: 1.2, 1.3, 8.2_

- [ ] 12. Build the dashboard UI
  - [ ] 12.1 Input form / CSV upload and assumption sliders (margin, holding cost, risk tolerance, holding period).
    - _Requirements: 5.1, 5.2_
  - [ ] 12.2 Vehicle Summary card, Price Comparison view (listing vs. max vs. resale vs. market value), Financial Summary, and Risk Summary (days-to-sell band); show price-source and market-value-proxy labels.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 2.4_
  - [ ] 12.3 Inventory comparison table with selectable ranking objective.
    - _Requirements: 6.1, 6.2_
  - [ ] 12.4 Top contributing factors display for each recommendation.
    - _Requirements: 7.5_

- [ ] 13. Verify performance targets
  - Measure single-vehicle evaluation latency (< 5 s p95) and assumption-change recompute (< 1 s p95); optimize if not met.
  - _Requirements: 8.1, 5.3_

- [ ] 14. Implement monitoring, retraining, and fairness checks
  - Log predictions with model versions; join realized outcomes when available; compute model + business metrics.
  - Implement drift and per-state fairness checks; add a rolling-window retraining trigger and a degradation trigger.
  - _Requirements: 9.1, 9.2, 9.3, 9.4_
