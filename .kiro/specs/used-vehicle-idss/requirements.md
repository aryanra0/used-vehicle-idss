# Requirements Document

## Introduction
This document defines the requirements for the Intelligent Decision Support System (IDSS) for Used Vehicle Acquisition, derived from the project PRD (MSE 436, Group 16). The system helps a used-car dealership decide whether to buy a candidate vehicle and the maximum price to pay, by predicting resale value, a days-to-sell band, and profitability, and applying user-adjustable business rules. Price models are trained on a **blend of multiple real vehicle-price datasets** (a large retail-listings source with VINs, a wholesale-auction source with condition and MMR, and a recent source for 2019+ coverage), harmonized to a common schema with a `source_channel` flag distinguishing wholesale from retail. A market-value benchmark is used where available (MMR) or engineered as a group-median-price proxy where absent; days-to-sell is derived from an industry make/segment benchmark. Requirements use the EARS format for acceptance criteria.

## Requirements

### Requirement 1: Vehicle Data Input
**User Story:** As a dealership buyer, I want to enter vehicle information manually or by CSV, so that I can evaluate one or many vehicles quickly.

#### Acceptance Criteria
1. WHEN a user submits a single vehicle with all required attributes THE SYSTEM SHALL accept the input and generate a recommendation.
2. WHEN a user uploads a CSV file THE SYSTEM SHALL validate each row against the documented input schema.
3. IF a CSV contains invalid rows THE SYSTEM SHALL process the valid rows and return a downloadable error report identifying each invalid row and the reason.
4. IF an optional attribute is missing THE SYSTEM SHALL impute a value rather than reject the record.
5. WHEN a user provides per-evaluation assumptions (holding cost, repair estimate) THE SYSTEM SHALL apply them to that evaluation.

### Requirement 2: Market-Value Benchmark
**User Story:** As a buyer, I want each vehicle compared to a market-value benchmark, so that predictions and the price comparison reflect what the vehicle is worth.

#### Acceptance Criteria
1. WHEN a vehicle is evaluated THE SYSTEM SHALL determine a market-value benchmark for that vehicle, preferring a real MMR value when available and otherwise using an engineered group-median-price proxy (by make/model/year).
2. WHEN the market-value benchmark is available THE SYSTEM SHALL compute a price-vs-benchmark delta and make it available as a feature and a display value.
3. IF no benchmark is available for a vehicle THE SYSTEM SHALL still produce a recommendation and flag the missing benchmark.
4. WHEN the benchmark is an engineered proxy rather than a real MMR value THE SYSTEM SHALL label it as such so the user understands it is derived, not independent.
5. THE SYSTEM SHALL compute any group-median-price proxy used as a model feature with cross-fold encoding so it does not leak the price target.

### Requirement 3: Prediction Engine
**User Story:** As a buyer, I want the system to predict resale value, time-to-sell, and profitability, so that I understand the financial outlook of a purchase.

#### Acceptance Criteria
1. WHEN a vehicle is evaluated THE SYSTEM SHALL predict expected resale price using a regression model trained on the blended dataset, and SHALL predict for a configured price channel (retail by default, wholesale optional).
2. WHEN a vehicle is evaluated THE SYSTEM SHALL predict a days-to-sell band using a classification model.
3. WHEN a vehicle is evaluated THE SYSTEM SHALL compute expected gross profit, ROI, and holding-cost impact from the predictions, user assumptions, and repair estimate.
4. WHEN a vehicle is evaluated THE SYSTEM SHALL output a Buy or Pass recommendation with a calibrated confidence score between 0 and 1.
5. THE SYSTEM SHALL only use features that are knowable before acquisition (no target leakage).
6. WHEN the same inputs and model version are provided THE SYSTEM SHALL produce identical outputs (reproducibility).

### Requirement 4: Decision Logic (Buy/Pass and Max Purchase Price)
**User Story:** As a buyer, I want a clear buy/pass call and a price ceiling, so that I know whether and how much to bid.

#### Acceptance Criteria
1. THE SYSTEM SHALL recommend Buy only IF expected ROI is greater than or equal to the target profit margin, AND expected gross profit is greater than or equal to the minimum dollar profit, AND model confidence is greater than or equal to the risk-tolerance threshold; OTHERWISE THE SYSTEM SHALL recommend Pass.
2. THE SYSTEM SHALL compute maximum purchase price as: PredictedResalePrice minus EstimatedRepairs minus TotalHoldingCost minus RequiredProfit, where TotalHoldingCost equals HoldingCostPerDay times PredictedDaysToSell and RequiredProfit equals TargetProfitMargin times PredictedResalePrice.
3. THE SYSTEM SHALL apply default thresholds of 15% target margin, $1,000 minimum profit, and 0.60 confidence, all overridable by the user.
4. THE SYSTEM SHALL bias decision thresholds toward caution to reflect the higher cost of overestimation versus underestimation.
5. THE M3 confidence model SHALL be trained to predict whether a vehicle, if bought at a wholesale discount below market value (default 20%), would clear the target margin; and its decision threshold SHALL be tuned on a validation set to maximize F1.
6. WHEN no listing price is supplied THE SYSTEM SHALL evaluate the vehicle at the wholesale acquisition price (market value less the acquisition discount).

### Requirement 5: Adjustable Assumptions and Scenario Planning
**User Story:** As an inventory manager, I want to change business assumptions and see updated results immediately, so that I can compare conservative and aggressive strategies.

#### Acceptance Criteria
1. THE SYSTEM SHALL let users adjust target profit margin, holding cost per day, risk tolerance, and target holding period.
2. WHEN a user changes any assumption THE SYSTEM SHALL recompute the recommendation, maximum price, and financial summary without a full page reload.
3. WHEN a user changes any assumption THE SYSTEM SHALL complete the recompute within 1 second at p95 using cached predictions.

### Requirement 6: Comparison and Ranking
**User Story:** As a manager, I want to compare and rank multiple vehicles, so that I can prioritize purchases.

#### Acceptance Criteria
1. THE SYSTEM SHALL display multiple evaluated vehicles in a single inventory table showing expected profit, risk, and days-to-sell band.
2. WHEN a user selects a ranking objective (expected profit, ROI, or lowest risk) THE SYSTEM SHALL sort the evaluated vehicles by that objective.

### Requirement 7: Dashboard and Transparency
**User Story:** As a buyer, I want a clear dashboard showing the recommendation and the numbers behind it, so that I can trust and defend the decision.

#### Acceptance Criteria
1. THE SYSTEM SHALL display a Vehicle Summary card with Buy/Pass, confidence, expected profit, and recommended maximum purchase price.
2. THE SYSTEM SHALL display a Price Comparison view showing listing price, recommended maximum purchase price, predicted resale price, and the market-value benchmark (MMR).
3. THE SYSTEM SHALL display a Financial Summary showing purchase price, estimated repairs, resale price, holding cost, and net profit.
4. THE SYSTEM SHALL display a Risk Summary showing the predicted days-to-sell band, a market demand indicator, and an overall risk level.
5. THE SYSTEM SHALL display the top contributing factors for each recommendation.

### Requirement 8: Performance and Scalability
**User Story:** As a buyer at an auction, I want fast results and batch screening, so that I can act within time pressure.

#### Acceptance Criteria
1. WHEN a single vehicle is evaluated THE SYSTEM SHALL return a prediction within 5 seconds at p95.
2. THE SYSTEM SHALL support bulk CSV upload of at least 1,000 rows per batch.

### Requirement 9: Retraining, Monitoring, and Fairness
**User Story:** As the system owner, I want the models kept accurate and fair over time, so that recommendations remain trustworthy.

#### Acceptance Criteria
1. THE SYSTEM SHALL support retraining on a rolling window when new labeled sales accumulate, or sooner on significant market shifts.
2. WHEN realized sale outcomes are available THE SYSTEM SHALL compare predicted resale price and profit against actual outcomes.
3. IF prediction accuracy degrades beyond a defined threshold THE SYSTEM SHALL flag a retraining and data-drift investigation.
4. THE SYSTEM SHALL track prediction error per state and flag systematic regional over- or under-valuation.

### Requirement 10: Data Preparation and Model Evaluation
**User Story:** As the team, I want the data prepared correctly and models validated before release, so that we do not ship a model worse than a simple baseline.

#### Acceptance Criteria
1. THE SYSTEM SHALL perform exploratory data analysis (EDA) on each source before modeling, profiling row counts, dtypes, value ranges, target skew, missingness, outliers, categorical cardinality, and the wholesale-vs-retail price gap, and SHALL persist an EDA summary artifact.
2. THE SYSTEM SHALL clean and harmonize each source to a common schema: normalize categorical casing/whitespace, standardize state codes, parse price and mileage strings to numbers, and split any transmission encoded in the model field.
3. THE SYSTEM SHALL deduplicate records within and across sources (by VIN where present, and by exact-row match otherwise).
4. THE SYSTEM SHALL filter impossible/outlier values using documented bounds for price, mileage, and year.
5. THE SYSTEM SHALL apply a documented missing-value policy per column, relying on the tree models' native NaN handling for features present in only some sources rather than dropping them.
6. THE SYSTEM SHALL apply a log transform to the skewed resale-price target for M1 and invert it on output, reporting error on the original dollar scale.
7. THE SYSTEM SHALL encode categoricals appropriately (ordinal for tree models; cross-fold target/frequency encoding for high-cardinality fields such as model), and SHALL standardize numeric features only for any linear baseline that requires it.
8. THE SYSTEM SHALL split data chronologically by sale date where dates exist and otherwise stratify by model year and source, and SHALL hold out a recent (2020+) slice for a dedicated recency evaluation.
9. THE SYSTEM SHALL evaluate resale price (M1) with MAE, MAPE, RMSLE, and R2; days-to-sell band (M2) with accuracy, macro-F1, and ROC-AUC; and buy/pass (M3) with F1 at the tuned threshold, ROC-AUC, AUC-PR, and calibration.
10. THE SYSTEM SHALL report M1 and M3 metrics broken down per source and on the recent (2020+) holdout, and SHALL report the M3 F1 alongside the trivial "always positive" F1 baseline.
11. THE SYSTEM SHALL block release of any model that does not beat its documented baseline by the required margin.

### Requirement 12: Multi-Source Data Integration
**User Story:** As the team, I want the multiple price datasets combined correctly, so that we gain volume and coverage without blurring different price levels or eras.

#### Acceptance Criteria
1. THE SYSTEM SHALL map each source dataset to a common schema (price, year, mileage, make, model, state, vin, condition, source_channel) and record each row's originating source.
2. THE SYSTEM SHALL add a `source_channel` feature (wholesale-auction vs retail-listing) so the model can learn the price-level offset between sources rather than averaging them.
3. THE SYSTEM SHALL retain source-specific columns (e.g., condition, MMR, VIN-derived fields) even when present in only some sources, without discarding them.
4. THE SYSTEM SHALL include model year as a feature so era differences across sources are represented.
5. THE SYSTEM SHALL validate that combining sources improves accuracy on the recent (2020+) holdout relative to any single source, and SHALL document the result; if it does not improve, the combination SHALL be reconsidered.

### Requirement 11: Days-to-Sell Band Derivation
**User Story:** As the team, I want a defensible days-to-sell estimate given our data, so that the recommendation includes a timing view without overclaiming precision.

#### Acceptance Criteria
1. THE SYSTEM SHALL derive the days-to-sell band from an industry make/segment benchmark joined to each vehicle.
2. THE SYSTEM SHALL present the days-to-sell output as a band — Fast (60 days or fewer), Moderate (61 to 90 days), Slow (91 to 120 days), or Very slow (over 120 days) — rather than an exact day count.
3. THE SYSTEM SHALL label the days-to-sell output as a benchmark-level estimate in the user interface.
