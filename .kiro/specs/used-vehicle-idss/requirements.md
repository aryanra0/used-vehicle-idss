# Requirements Document

## Introduction
This document defines the requirements for the Intelligent Decision Support System (IDSS) for Used Vehicle Acquisition, derived from the project PRD (MSE 436, Group 16). The system helps a used-car dealership decide whether to buy a candidate vehicle and the maximum price to pay, by predicting resale value, a days-to-sell band, and profitability, and applying user-adjustable business rules. Models are trained on a **single real dataset**, `car_prices.csv` (~558k US wholesale/auction records with a real MMR benchmark and condition grade). The real Manheim **MMR** is used both as a model feature and, for user-entered vehicles without one, as a make/model/year median lookup; days-to-sell is derived from an industry make benchmark. Each prediction carries a confidence score, and abnormal inputs/outputs are surfaced as advisory data-quality flags. Requirements use the EARS format for acceptance criteria.

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
1. WHEN a vehicle is evaluated THE SYSTEM SHALL determine its MMR benchmark, preferring a user-provided value, then a live feed (if configured), otherwise a make/model/year median from the training data with progressive fallback (make/model/year → make/model → make → global).
2. WHEN the market-value benchmark is available THE SYSTEM SHALL compute a price-vs-benchmark delta and make it available as a feature and a display value.
3. IF no benchmark is available for a vehicle THE SYSTEM SHALL still produce a recommendation and flag the missing benchmark.
4. WHEN the benchmark comes from a coarse fallback (make-level or global) THE SYSTEM SHALL reflect that in a lower market-value confidence and note it.
5. THE SYSTEM SHALL use the real MMR as a model feature (`market_value`); because MMR is an external, pre-sale benchmark and not the sale price, this is not target leakage.

### Requirement 3: Prediction Engine
**User Story:** As a buyer, I want the system to predict resale value, time-to-sell, and profitability, so that I understand the financial outlook of a purchase.

#### Acceptance Criteria
1. WHEN a vehicle is evaluated THE SYSTEM SHALL predict expected resale price using a regression model trained on the single-source dataset with the real MMR as a feature; the estimate is a wholesale value.
2. WHEN a vehicle is evaluated THE SYSTEM SHALL predict a days-to-sell band using a classification model.
3. WHEN a vehicle is evaluated THE SYSTEM SHALL compute expected gross profit, ROI, and holding-cost impact from the predictions, user assumptions, and repair estimate.
4. WHEN a vehicle is evaluated THE SYSTEM SHALL output a Buy or Pass recommendation with a calibrated confidence score between 0 and 1.
5. THE SYSTEM SHALL only use features that are knowable before acquisition (no target leakage); the sale price is the sole leakage-excluded column and MMR is permitted as a feature.
6. WHEN the same inputs and model version are provided THE SYSTEM SHALL produce identical outputs (reproducibility).
7. THE SYSTEM SHALL attach a per-prediction confidence (score, level, and basis) to the resale price, market value, days-to-sell band, and buy/pass call; the buy/pass confidence SHALL be the lower of the profit-model probability and the resale-estimate reliability.
8. WHEN the resale estimate is low-confidence (few comparables or large divergence from MMR) THE SYSTEM SHALL reconcile it toward the MMR benchmark in proportion to confidence (a shrink, not a hard cap).

### Requirement 4: Decision Logic (Buy/Pass and Max Purchase Price)
**User Story:** As a buyer, I want a clear buy/pass call and a price ceiling, so that I know whether and how much to bid.

#### Acceptance Criteria
1. THE SYSTEM SHALL recommend Buy only IF expected ROI is greater than or equal to the target profit margin, AND expected gross profit is greater than or equal to the minimum dollar profit, AND model confidence is greater than or equal to the risk-tolerance threshold; OTHERWISE THE SYSTEM SHALL recommend Pass.
2. THE SYSTEM SHALL compute maximum purchase price as: PredictedResalePrice minus EstimatedRepairs minus TotalHoldingCost minus RequiredProfit, where TotalHoldingCost equals HoldingCostPerDay times PredictedDaysToSell and RequiredProfit equals TargetProfitMargin times PredictedResalePrice.
3. THE SYSTEM SHALL apply default thresholds of 15% target margin, $1,000 minimum profit, and 0.60 confidence, all overridable by the user.
4. THE SYSTEM SHALL bias decision thresholds toward caution to reflect the higher cost of overestimation versus underestimation.
5. THE M3 confidence model SHALL be trained to predict whether a vehicle, if bought at a wholesale discount below market value (default 20%), would clear the target margin; and its decision threshold SHALL be tuned on a validation set to maximize F1.
6. WHEN no listing price is supplied THE SYSTEM SHALL evaluate the vehicle at the wholesale acquisition price (market value less the acquisition discount).
7. THE SYSTEM SHALL make the Buy/Pass call on face-value economics; abnormal-input/output warnings (abnormally low price, implausible ROI, resale-vs-MMR divergence, zero mileage) SHALL be surfaced as advisory data-quality flags that do NOT change the verdict.
8. THE SYSTEM SHALL present the maximum purchase price as a ceiling (walk-away limit) and provide plain-language guidance consistent with the verdict (pay the listing, negotiate below the ceiling, or hold off) — never advising a payment above the listing price.

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
6. THE SYSTEM SHALL display the per-prediction confidence (resale, market value, days-to-sell, buy/pass) with its level and basis, any advisory data-quality flags, and the price guidance line.

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
1. THE SYSTEM SHALL clean the source into the model schema: parse price and mileage strings to numbers, normalize categorical casing/whitespace, and sanitize the contaminated `transmission` column (keep only valid values).
2. THE SYSTEM SHALL filter impossible/outlier values using documented bounds for price, mileage, and year, and SHALL de-duplicate records.
3. THE SYSTEM SHALL drop rows missing any required field (price, mmr, year, mileage, make, model) and leave optional fields (e.g., condition) as NaN for the tree models to handle natively.
4. THE SYSTEM SHALL apply a log transform to the skewed resale-price target for M1 and invert it on output, reporting error on the original dollar scale.
5. THE SYSTEM SHALL encode categoricals with ordinal encoding for the tree models, and SHALL standardize numeric features only for any linear baseline that requires it.
6. THE SYSTEM SHALL split the data into train / validation / test, using the validation set to tune the M3 decision threshold and holding out the test set for final metrics; splits SHALL be persisted.
7. THE SYSTEM SHALL evaluate resale price (M1) with MAE, MAPE, RMSLE, and R2 against an MMR-quote baseline; days-to-sell band (M2) with accuracy and macro-F1; and buy/pass (M3) with F1 at the tuned threshold, ROC-AUC, AUC-PR, and calibration, reported alongside the trivial "always positive" F1 baseline.
8. THE SYSTEM SHALL report a per-state error breakdown for M1 (fairness).
9. THE SYSTEM SHALL block release of any model that does not beat its documented baseline by the required margin.

### Requirement 12: Single-Source Data
**User Story:** As the team, I want a single coherent price dataset, so that model naming is consistent and the resale target is comparable to the MMR benchmark.

#### Acceptance Criteria
1. THE SYSTEM SHALL train all models on one real source (`car_prices.csv`), using its consistent model naming so benchmark lookups do not fall back to a coarse make-level median.
2. THE SYSTEM SHALL use the source's wholesale price basis for both the resale target and the MMR benchmark, so the two are directly comparable.
3. THE SYSTEM SHALL use the real MMR both as a model feature and, for user-entered vehicles without an MMR, as a make/model/year median lookup.
4. THE SYSTEM SHALL include model year as a feature so vehicle era is represented.
5. THE SYSTEM SHALL flag vehicles outside the source's coverage (model years beyond 2015) with an out-of-coverage warning.

Note: an earlier version blended three sources with a `source_channel` flag; it was retired because inconsistent naming broke benchmark lookups and mixed retail/wholesale price levels made the resale estimate ambiguous relative to the wholesale MMR.

### Requirement 11: Days-to-Sell Band Derivation
**User Story:** As the team, I want a defensible days-to-sell estimate given our data, so that the recommendation includes a timing view without overclaiming precision.

#### Acceptance Criteria
1. THE SYSTEM SHALL derive the days-to-sell band from an industry make/segment benchmark joined to each vehicle.
2. THE SYSTEM SHALL present the days-to-sell output as a band — Fast (60 days or fewer), Moderate (61 to 90 days), Slow (91 to 120 days), or Very slow (over 120 days) — rather than an exact day count.
3. THE SYSTEM SHALL label the days-to-sell output as a benchmark-level estimate in the user interface.
