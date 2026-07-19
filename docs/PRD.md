# Product Requirements Document (PRD)
## IDSS for Used Vehicle Acquisition

| Field | Value |
|---|---|
| Document status | Draft v6 (multi-source data blend; full preprocessing pipeline) |
| Course / Team | MSE 436 — Group 16 |
| Product type | Intelligent Decision Support System (IDSS) |
| Last updated | 2026-07-17 |

---

## 1. Overview

### 1.1 Problem Statement
Used-car dealerships evaluate hundreds of vehicle listings each day across Craigslist, Facebook Marketplace, auctions, and dealer exchanges. Buy/pass decisions rely heavily on individual employee experience, incomplete market information, and manual price comparisons. This leads to:

- Overpaying for inventory, which compresses margins.
- Slow inventory turnover and capital tied up in aging stock.
- Inconsistent decisions between buyers on comparable vehicles.
- No systematic estimate of downstream risk (time-to-sell, demand).

Dealerships need a system that fuses historical sales data and market benchmarks to recommend whether to buy a vehicle and the maximum price worth paying, with a transparent, adjustable financial rationale.

### 1.2 Product Vision
Build an Intelligent Decision Support System (IDSS) that helps used-car dealerships make faster, more consistent, and data-driven acquisition decisions by predicting resale value, expected time-to-sell, and expected profitability, while letting users adjust business assumptions and immediately see the effect on the recommendation.

### 1.3 Decision the System Supports
The IDSS augments (does not replace) the human buyer. For a candidate vehicle it answers a single primary decision — **Buy or Pass** — supported by a **recommended maximum purchase price** and a quantified expectation of **profit, time-to-sell, and risk**. User-defined constraints (target profit margin, holding cost, risk tolerance, holding period) shift recommendations along a spectrum from **aggressive** (higher inventory, lower margin) to **conservative** (fewer, higher-margin deals). The buyer retains final authority.

### 1.4 Prediction Task Summary
| Aspect | Definition |
|---|---|
| Task type | Regression (resale price) + classification (days-to-sell band; buy/pass). |
| Entity | A used vehicle's specifications (make, model, year, condition, mileage, and more). |
| Outcomes | Buy/pass decision plus expected profit, recommended max purchase price, and repair-cost estimate. |
| Resale label | Actual sold price from historical sales data (real transactions, not asking prices). |
| Days-to-sell label | Benchmark-level: average days-to-sell by make/segment (industry data), not per-car. |

### 1.5 Definitions
| Term | Definition |
|---|---|
| Resale price | Predicted price the dealer can sell the vehicle for after reconditioning. |
| Days-to-sell (DTS) | Predicted band of days from acquisition to sale: Fast (≤60), Moderate (61–90), Slow (91–120), Very slow (>120). |
| MMR | Manheim Market Report value — a wholesale market-value benchmark included per vehicle in the primary dataset. |
| Holding cost | Daily cost of keeping a vehicle in inventory (floor-plan interest, lot, insurance). |
| Max purchase price | Highest acquisition price that still meets the user's target margin given predicted resale, repairs, and holding cost. |
| Gross profit | Resale price − purchase price − estimated repairs − total holding cost. |
| ROI / ROIC | Gross profit ÷ total invested capital (purchase + repairs). |
| Confidence score | Calibrated model probability attached to the Buy/Pass recommendation. |

---

## 2. Goals and Non-Goals

### 2.1 Business Goals
- Increase average gross profit per vehicle acquired.
- Reduce losses from overpaying for inventory.
- Improve inventory turnover (reduce average days-to-sell).
- Maximize return on invested capital (ROIC).
- Reduce manual appraisal time per vehicle.
- Improve decision consistency across buyers.

### 2.2 User Goals
Enable a buyer to quickly answer:
- Should I buy this vehicle?
- What is the maximum price I should pay?
- How much profit should I expect?
- How risky is this purchase?
- Roughly how long will it stay in inventory?

### 2.3 Non-Goals (for this version)
- Not an inventory-management or CRM system.
- Not a financing/lending recommendation engine.
- Does not execute purchases or negotiate automatically.
- Does not perform photo-based damage assessment or VIN scanning (see Future Enhancements).

---

## 3. Target Users

### 3.1 Primary
- Vehicle acquisition managers and dealership buyers.
- Inventory managers at used-vehicle dealerships.
- Independent used-car dealers.

### 3.2 Secondary
- Small automotive wholesalers.
- Fleet purchasing teams.
- Auction buyers.

### 3.3 Primary Persona
**Maria — Acquisition Manager, independent dealership.** Evaluates 40–80 listings/day, often on mobile at auctions with limited time. Needs a fast, defensible buy/pass call and a price ceiling she can negotiate against. Distrusts black-box outputs; wants to see the numbers behind a recommendation.

---

## 4. User Stories

Each story is written as: *As a [user], I want [capability], so that [outcome].* Acceptance criteria live in the requirements document.

- **US-1 (Evaluation):** As a buyer, I want to enter vehicle information and immediately see whether purchasing is profitable, so I can make a fast decision.
- **US-2 (Pricing):** As a buyer, I want a recommended maximum purchase price, so I know my negotiation ceiling without eroding profit.
- **US-3 (Scenario planning):** As an inventory manager, I want to change target margin, holding cost, and risk tolerance, so I can compare conservative vs. aggressive strategies.
- **US-4 (Comparison):** As a manager, I want to compare multiple vehicles side by side, so I can prioritize which to buy first.
- **US-5 (Bulk triage):** As a buyer, I want to upload a CSV of listings and get ranked recommendations, so I can screen a large batch quickly.
- **US-6 (Transparency):** As a buyer, I want to see the main factors behind a recommendation and how listing/max/resale prices compare, so I can trust and defend the decision.

---

## 5. Functional Requirements (Summary)
Full, testable acceptance criteria are maintained in `.kiro/specs/used-vehicle-idss/requirements.md`. At a high level the system shall:

- Accept single-vehicle manual entry and bulk CSV upload, with per-evaluation assumptions (holding cost, repair estimate).
- Predict resale price, a days-to-sell band, and profitability; output a Buy/Pass recommendation with a calibrated confidence score.
- Compute a recommended maximum purchase price and full financials (gross profit, ROI, holding cost).
- Let users adjust target margin, holding cost, risk tolerance, and holding period, and recompute instantly.
- Compare and rank multiple vehicles.
- Display Vehicle Summary, Price Comparison, Financial Summary, and Risk Summary, plus the top contributing factors.

---

## 6. Machine Learning Models

### 6.1 Model Summary
| ID | Model | Task | Target | Primary metric(s) |
|---|---|---|---|---|
| M1 | Resale Price Prediction | Regression | Actual sold price ($) | MAE, MAPE, RMSLE, R² |
| M2 | Days-to-Sell Band | Multi-class classification | Sale-time band in days: Fast ≤60, Moderate 61–90, Slow 91–120, Very slow >120 | Accuracy, F1, ROC-AUC |
| M3 | Profitability / Buy-Pass | Binary classification | P(clears target margin if bought at a wholesale discount below market value) → Buy/Pass | F1, ROC-AUC, AUC-PR, calibration (report trivial-baseline F1) |

### 6.2 Candidate Approach (informed by literature)
- **Baselines first:** linear regression (M1), majority-class / logistic regression (M2, M3) to set a floor.
- **Primary models:** gradient-boosted trees — XGBoost / LightGBM — which are the established best performers for tabular used-car price prediction; Random Forest is a strong, interpretable alternative and performed best in the referenced sale-time study.
- **Blended, multi-source training:** M1 is trained on a harmonized blend of three real datasets (see §7) with a `source_channel` flag (wholesale vs retail) so the model learns the price-level offset instead of averaging it. Model year is a feature so era differences are represented.
- **Price target handling (M1):** apply a log transform to the (right-skewed) price and invert on output; evaluate error on the original dollar scale.
- **Preprocessing (full pipeline, see §7.5):** EDA/profiling, schema harmonization, string parsing, dedup, outlier removal, documented missing-value policy, categorical encoding (ordinal for trees; cross-fold target/frequency encoding for high-cardinality `model` and the market-value proxy), standardization only for linear baselines, and engineered features (vehicle age, mileage-per-year, VIN-decoded specs, group-median market value, regional price index).
- **Modular design:** separate price (M1), time-to-sell (M2), and decision logic (M3) for interpretability. M3 consumes M1 output plus features and business rules.
- **M3 label (wholesale acquisition):** dealerships buy below market value and resell. M3's label is whether a car, if bought at a typical wholesale discount below its market value (MMR, default 20%), would still resell for enough to clear the target margin. This reflects the real acquisition decision and is learnable from features. An earlier framing ("resells above its own MMR") was near-noise because MMR already predicts the sale price. M3's probabilities are **calibrated** and its decision threshold is **tuned on a validation set to maximize F1** (not fixed at 0.5).

### 6.3 Features
All features are available at prediction time and knowable before acquisition (no target leakage).

- **Harmonized raw:** year, make, model, mileage, state, condition (where present), `source_channel`.
- **VIN-decoded (where a VIN exists):** body, cylinders, fuel type, drivetrain — recovers fields the retail source lacks.
- **Engineered:** vehicle age (current year − model year); mileage-per-year; regional (state) price index; model-frequency / brand tier; group-median market-value proxy (make/model/year, computed cross-fold to avoid leakage); seasonal flag where sale dates exist.
- **Days-to-sell join:** average days-to-sell by make/segment from the industry benchmark file, used to derive the M2 band label.
- **Adjustable parameters (user, not learned):** target profit margin, risk tolerance, holding cost, holding period.
- Features present in only some sources (e.g., condition) are left blank elsewhere; the tree models handle missing values natively.

### 6.4 Evaluation and Targets
- Split **chronologically by sale date where dates exist**, else stratified by model year and source; always reserve a **recent (2020+) holdout** for a dedicated recency test.
- M1 evaluated with MAE, MAPE, RMSLE, R² — reported **overall, per source, and on the 2020+ holdout**; M2 with accuracy, macro-F1, ROC-AUC; M3 with F1 (at the tuned threshold), ROC-AUC, AUC-PR, and calibration (Brier score).
- **Combination check:** the blended model must beat any single source on the 2020+ holdout; otherwise the blend is reconsidered.
- **Honest reporting for M3:** because the profitable class is the majority (~72%), a naive "always Buy" classifier already scores a high F1 (~0.84). M3's F1 is therefore always reported **alongside that trivial-baseline F1 and the threshold-independent AUC/AUC-PR**, so a high F1 is not mistaken for skill it does not have. Current results: F1 ≈ 0.88, ROC-AUC ≈ 0.86, AUC-PR ≈ 0.93 (trivial-baseline F1 ≈ 0.84).
- All models must **beat their baseline** by a documented margin before release; per-region (state) error tracked for fairness.

### 6.5 Retraining and Learning Loop
- Retrain on a rolling window when new labeled sales accumulate, or sooner on significant market shifts.
- The system functions as a lightweight feedback loop: realized sale outcomes and dealer feedback on recommendations feed future training.

### 6.6 Error Costs and Fairness
- **Asymmetric error cost:** overestimating a vehicle's value is worse than underestimating it. Overestimation risks buying cars that won't sell for profit (capital loss); underestimation is a missed opportunity. Model selection and decision thresholds shall reflect this asymmetry.
- **Regional fairness:** the model shall avoid systematically over- or under-valuing vehicles from particular regions; per-state error shall be evaluated and monitored.

### 6.7 Assumptions and Known Limitations
- **Blended price levels:** training mixes wholesale (sold) and retail (asking) prices; the `source_channel` flag lets the model separate them, and the tool reports a configured channel (retail by default). Where a source has asking rather than sold prices, predictions reflect asking prices.
- **Condition coverage:** condition exists only for the wholesale (`car_prices`) rows; it is blank for the retail sources and cannot be engineered.
- **Market value:** a real MMR exists only for the wholesale rows; elsewhere a **group-median-price proxy** is used and labeled as derived (not an independent benchmark).
- **Recency:** most rows are ≤2018; only ~1,258 are model year 2020+. Predictions for 2020+ are supported but lower-confidence, and the out-of-coverage warning triggers beyond model year 2024. Truly current prices still require a live feed.
- Days-to-sell is available only as a **make/segment benchmark average**, not a per-car duration; the day-scale bands (≤60 / 61–90 / 91–120 / >120) are calibrated to the observed benchmark distribution (~40–105 days, median ~71).

### 6.8 Decision Logic (Buy/Pass and Max Purchase Price)
These are the default rules; users can adjust the parameters.

**Buy/Pass rule.** For the vehicle at the price under consideration, compute expected gross profit and ROI, then recommend **Buy** only if all three hold; otherwise **Pass**:
1. Expected ROI ≥ target profit margin (default 15%).
2. Expected gross profit ≥ minimum dollar profit (default $1,000).
3. Model confidence ≥ the user's risk-tolerance threshold (default 0.60).

**Maximum purchase price.** Worked backward from predicted resale value:

```
MaxPurchasePrice = PredictedResalePrice − EstimatedRepairs − TotalHoldingCost − RequiredProfit
  TotalHoldingCost = HoldingCostPerDay × PredictedDaysToSell
  RequiredProfit    = TargetProfitMargin × PredictedResalePrice   (default 15%)
```

**Worked example.** Predicted resale $12,000; repairs $800; holding cost $20/day × 45 days = $900; target margin 15% → required profit $1,800.
MaxPurchasePrice = 12,000 − 800 − 900 − 1,800 = **$8,500**. Recommend Buy only if the vehicle can be acquired at or below $8,500.

Note: the ROI and dollar-profit thresholds are cost-sensitive by design (Section 6.6) — the defaults lean conservative to avoid overpaying.

**Default purchase scenario.** When the user does not supply a listing price, the system evaluates the vehicle at a typical **wholesale acquisition price** — a discount below market value (MMR), default 20% — reflecting that dealers buy below market. When a listing price is supplied, that price is used directly.

---

## 7. Data Sources

Price models train on a **blend of three real datasets**, harmonized to a common schema with a `source_channel` flag. Tree models handle features present in only some sources via native missing-value support, so no source-specific column is discarded.

### 7.1 Base — Retail Listings (`true_car_listings.csv`)
- ~852,000 real US retail listings; model years ≤2018. Largest, cleanest real source.
- Fields: Price (asking), Year, Mileage, City, State, **VIN**, Make, Model.
- Strengths: scale, real signal (price rises with year, falls with mileage), and VINs that enable decoding of body/engine/fuel/drivetrain. Cleaning: split transmission out of the model string; standardize state codes.

### 7.2 Wholesale + Condition + MMR (`car_prices.csv`)
- ~558,000 real wholesale/auction records, ≤2015. Contributes the only **condition** signal, real **sold prices**, and a real **MMR** market-value benchmark.
- Tagged `source_channel = wholesale`.

### 7.3 Recency Source (`used_cars.csv`)
- ~4,000 real retail records reaching **2013–2024**; contributes recent (2019+) coverage plus fuel/transmission/accident/title.

### 7.4 Days-to-Sell Benchmark — Edmunds "Days To Turn" (`2016-10-dtt.xls`)
- Monthly average days-to-sell by manufacturer/make/segment; used to derive the M2 band. Aggregate, not per-car.

### 7.5 Preprocessing Pipeline (run before modeling)
Ordered stages, each producing a versioned artifact:
1. **EDA/profiling** per source (ranges, skew, missingness, outliers, cardinality, duplicate/overlap scan, wholesale-vs-retail price gap) → persisted EDA summary.
2. **Schema harmonization** to a common schema + `source_channel` + originating-source tag.
3. **Parsing/normalization** — `$`/comma prices, "mi." mileage, transmission-from-model split, casing/whitespace, state codes.
4. **Dedup** — by VIN where present, else exact-row, within and across sources.
5. **Outlier/sanity filtering** — documented price/mileage/year bounds.
6. **Missing-value policy** — per column; keep source-only columns as NaN (trees handle natively).
7. **Feature engineering** — VIN decode, group-median market-value proxy (cross-fold), regional index, age, miles/year.
8. **Target transform + encoding** — log price target; ordinal encoding for trees; cross-fold target/frequency encoding for high-cardinality fields; standardization only for linear baselines.
9. **Splitting** — chronological by sale date where available, else stratified by year/source; reserve a recent (2020+) holdout.
- Maintain a data dictionary; record dataset versions, source composition, and model version with each prediction (reproducibility).

### 7.6 Rejected Sources
- **`car_sales_data.csv` (+ duplicate)** and the other synthetic files — randomized make/model (e.g., "Nissan F-150", "Tesla … Petrol Manual"), price uncorrelated with year/mileage; no usable signal; excluded.
- **Moroccan used-cars dataset** — wrong market and currency (Moroccan dirham); excluded.

### 7.7 Optional / Future Sources
- **`Car Sales.xlsx`** (buyer demographics) — optional demand/segmentation side-analysis, not merged into the pricing model.
- **MarketCheck / Auto.dev API (future)** — live current-market prices; the only path to truly "today's" pricing (see §6.7 recency limitation).

---

## 8. System Workflow

1. User enters vehicle information (manual entry or bulk CSV upload) plus assumptions (holding cost, repair estimate).
2. System looks up the market-value benchmark (real MMR where available, else the group-median proxy) and the make/segment days-to-sell benchmark.
3. Features are engineered from inputs plus benchmarks.
4. Models produce resale value (M1), days-to-sell band (M2), and profitability (M3), in real time for the individual vehicle.
5. Business rules compute maximum purchase price, ROI, and Buy/Pass under the user's constraints.
6. Dashboard updates instantly; user can adjust assumptions and re-evaluate.
7. After sale, realized outcomes feed monitoring and the retraining/feedback loop.

---

## 9. Non-Functional Requirements
| Category | Requirement |
|---|---|
| **Performance** | Single-vehicle prediction latency < 5 s (p95); assumption changes recompute in < 1 s (p95) using cached predictions. |
| **Scalability** | Support real-time single-vehicle evaluation and bulk CSV upload of at least 1,000 rows per batch. |
| **Availability** | Available during dealership business hours; document target uptime. |
| **Reliability** | Scheduled retraining on a rolling window; automated monitoring for model drift and data-quality anomalies, with alerting. |
| **Transparency** | Every recommendation exposes its key contributing factors, the price comparison, and the assumptions used. |
| **Fairness** | Per-state prediction error monitored to prevent systematic regional over/under-valuation. |
| **Security/Privacy** | Secure storage of any API keys and user data; no secrets in source control. |
| **Usability** | Core evaluation flow completable on a laptop or tablet without training. |

---

## 10. Success Metrics

### 10.1 Model Metrics
- M1: MAE, MAPE, RMSLE, R² on sold price; per-state error for fairness.
- M2: accuracy, macro-F1, ROC-AUC on the sale-time band.
- M3: F1 (at the tuned threshold) reported with the trivial "always Buy" F1 baseline, plus ROC-AUC, AUC-PR, and calibration on buy/pass. AUC/AUC-PR are the primary skill indicators since F1 is inflated by class balance.
- All models must beat their baseline by a documented margin before release.

### 10.2 Business Metrics
- Average gross profit per car acquired.
- Inventory turnover rate.
- Percentage of purchased vehicles sold within the target 30–60 day window.
- Return on invested capital (ROIC).
- Reduction in losses from overpaying for vehicles.
- Increase in successful purchases meeting target profit margins.
- Dealer adoption rate and evaluations per user.

### 10.3 Evaluation Method
Offline: back-test on the chronologically held-out recent data; evaluate decisions on realized sale price and overall profit. Online (future): compare predictions against actual outcomes after sale; significant degradation triggers retraining and a data-drift investigation. Dealer feedback is collected to improve models and user trust.

---

## 11. Risks and Mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R-1 | Days-to-sell is only a make/segment benchmark, not per-car. | Coarse time-to-sell and holding-cost estimates. | Present as a band with a benchmark caveat; let users override holding period; seek per-car listing dates as future work. |
| R-2 | Primary data is 2014–2015, not current. | Predictions reflect an older market. | Frame as training/demo data; add live data (MarketCheck) for a production version; retrain when newer data is available. |
| R-3 | Limited repair-cost information. | Distorted profit estimates. | User-editable repair input; document default assumptions; sensitivity display. |
| R-4 | Regional markets diverge; possible regional bias. | Poor local accuracy / unfair valuations. | State features + per-state evaluation and monitoring. |
| R-5 | Data-quality issues (missing values, inconsistent casing, outliers). | Degraded model accuracy. | Documented cleaning pipeline; outlier filters; imputation. |
| R-6 | Users over-trust the model. | Bad decisions on low-confidence cases. | Show confidence, factors, and price comparison; position as decision support. |
| R-7 | Asymmetric cost: overestimation. | Buying cars that won't sell for profit; capital loss. | Cost-sensitive thresholds favoring caution (Section 6.6). |

---

## 12. Future Enhancements
- Acquire per-car listing/entry dates to train a true per-vehicle days-to-sell model (survival analysis or probability-of-sale-within-N-days).
- Integrate the MarketCheck API for live comparables and current market pricing.
- Repair-cost estimation via computer vision from vehicle photos.
- VIN decoding for automatic feature extraction.
- Demand/segmentation analysis using the retail buyer-demographics dataset.
- Negotiation assistant suggesting an opening offer.
- Expanded explainable-AI views of recommendation drivers.

---

## 13. MVP Scope

### 13.1 In Scope
- Manual vehicle entry and bulk CSV upload, with holding-cost and repair assumptions.
- Real-time predictions: resale price (M1), days-to-sell band (M2), profitability (M3).
- Buy/Pass recommendation with calibrated confidence and top factors.
- Recommended maximum purchase price.
- Adjustable target margin, holding cost/period, and risk tolerance.
- Dashboard: Vehicle Summary card, Price Comparison view, Financial Summary, Risk Summary.
- Multi-vehicle comparison and ranking (inventory table).

### 13.2 Out of Scope
- Dealer login/accounts and role management.
- Inventory management and CRM integration.
- Financing recommendations.
- Vehicle photo analysis and automatic VIN scanning.
- Live market data integration.

### 13.3 MVP Acceptance
The MVP is accepted when: (a) a user can evaluate a single vehicle and a CSV batch end to end; (b) M1, M2, and M3 beat their baselines by the documented margin on the chronologically held-out data; (c) recommendations, max price, and financials update within the latency targets; (d) each recommendation displays confidence, key factors, and the price comparison; and (e) per-state error is reported for M1.

---

## 14. Open Questions
- Confirm the default Buy/Pass thresholds (15% ROI, $1,000 minimum profit, 0.60 confidence) match the dealership's real acquisition strategy.
- Sale-time bands are set to Fast (≤60 days), Moderate (61–90), Slow (91–120), Very slow (>120), derived from the observed benchmark distribution (median ~71 days) and standard dealer overage practice; confirm these thresholds with the dealership. A simpler 3-band split (Fast / Moderate / Slow >90) is available if preferred.
- How is the repair-cost estimate produced in the MVP — user-entered only, or partly modeled?
- What default holding-cost assumptions ship as defaults, and who sets them?
- What accuracy margin over baseline defines "success" for each model?
- What is the acceptable per-state error gap before it is flagged as unfair?

---

## 15. Appendix

### 15.1 Expert Consultation
**Keith Fernandez — Data Engineer, Amazon Demand Forecasting** (co-op mentor). Helped reframe the problem from a pure prediction task into a decision-support system focused on inventory, risk, and timing constraints. Key guidance: the value of forecasting comes from how predictions drive operational decisions, which shaped the buy/pass framework and the modular design separating price, time-to-sell, and decision logic.

### 15.2 Key Reference
Ahaggach, H., Abrouk, L., Foufou, S., & Lebon, E. (2022). *Predicting Car Sale Time with Data Analytics and Machine Learning.* Product Lifecycle Management (PLM in Transition Times), pp. 399–409. DOI: 10.1007/978-3-031-25182-5_39. Basis for framing days-to-sell as a classification into sale-time bands and for the finding that tree-based models (Random Forest) perform well on used-vehicle sale-time prediction.
