# IDSS for Used Vehicle Acquisition

An Intelligent Decision Support System (IDSS) that helps used-car dealerships decide
**whether to buy a candidate vehicle and the maximum price to pay**. It predicts resale
value, a days-to-sell band, and profitability, then applies user-adjustable business
rules to produce a **Buy / Pass** recommendation with a recommended maximum purchase
price and a per-prediction confidence breakdown.

Course project — MSE 436, Group 16.

## What it does
- Predicts wholesale **resale value** (M1), a **days-to-sell band** (M2), and **buy/pass
  profitability** (M3).
- Anchors every vehicle to its **MMR** (Manheim Market Report) wholesale benchmark.
- Produces a **face-value Buy / Pass** call from ROI, gross profit, and confidence.
- Shows a **confidence score for each prediction**, and flags inputs/outputs that don't
  add up (abnormally low price, implausible ROI, valuation divergence) as advisory
  warnings that do not override the verdict.
- Recommends a **maximum purchase price** (a negotiation ceiling) and explains what to
  actually pay.

## Architecture
- **Backend:** Python + scikit-learn (HistGradientBoosting), served via **FastAPI**
  (`src/idss/api`).
- **Frontend:** **Next.js / React** dashboard (`web/`).
- **Models:** M1 resale (regression), M2 days-to-sell band (classification), M3 buy/pass
  (calibrated classification), plus an MMR lookup and the Edmunds days-to-turn benchmark.

## Data
Trained on a **single real source**: `car_prices.csv` (~558k US wholesale/auction records,
model years ~1990–2015). It is the only source with a real **MMR** benchmark and a
**condition** grade, it uses consistent model naming, and every row is a wholesale sale —
so the resale target and the MMR benchmark are directly comparable. Days-to-sell comes
from the Edmunds "Days To Turn" make-level benchmark (`2016-10-dtt.xls`).

Earlier iterations blended three sources; that was dropped in favor of the single coherent
source (see `data/README.md`). The other CSVs remain in `data/raw/` but are not used for
training.

## The three models
| ID | Model | Task | Target |
|----|-------|------|--------|
| M1 | Resale price | Regression | Wholesale sold price ($) |
| M2 | Days-to-sell band | Classification | Fast ≤60 / Moderate 61–90 / Slow 91–120 / Very slow >120 |
| M3 | Profitability / Buy-Pass | Calibrated classification | P(clears target margin if bought ~20% below MMR) |

MMR is used both as a **model feature** (the single strongest predictor of sale price) and
as a make/model/year **lookup** at serve time.

### Current metrics (held-out test set)
- **M1:** MAE ~$956, MAPE 11.4%, R² 0.966 — beats the "just quote MMR" baseline (MAE ~$1,091).
- **M2:** accuracy ~1.0 (the band is essentially a deterministic function of the make benchmark).
- **M3:** F1 0.89, ROC-AUC 0.84, AUC-PR 0.94 (trivial "always Buy" F1 0.87; positive rate 0.77).

## Decision logic (defaults, user-adjustable)
Recommend **Buy** only if all hold, else **Pass**:
1. Expected ROI ≥ target margin (default 15%)
2. Expected gross profit ≥ minimum (default $1,000)
3. Confidence ≥ risk tolerance (default 0.60)

```
MaxPurchasePrice = PredictedResale − Repairs − (HoldingCostPerDay × PredictedDaysToSell) − (TargetMargin × PredictedResale)
```

When no listing price is supplied, the vehicle is evaluated at a wholesale acquisition
price (default 20% below MMR). The max purchase price is a **ceiling**, not a target —
when a listing price is below it you pay the listing, not the ceiling.

### Confidence and data-quality flags
- Each prediction (resale, market value, days-to-sell, buy/pass) carries its own
  reliability **score, level, and basis**.
- Buy/pass confidence is the weaker of the profit-model probability and the
  resale-estimate reliability.
- A low-confidence resale estimate is **reconciled toward MMR** (a confidence-weighted
  shrink, not a hard cap), so rare/exotic vehicles are anchored to the benchmark instead
  of being trusted blindly.
- **Advisory flags** — abnormally low price (likely salvage/branded title), implausible
  ROI, resale-vs-MMR divergence, zero mileage — are surfaced prominently but do **not**
  change the face-value Buy/Pass verdict.

## Getting started
Prerequisites: Python 3.9+ and Node 18+.

```bash
# 1) Python environment + dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Train the models (writes artifacts to models/ and splits to data/processed/)
cd src && PYTHONPATH=. python3 -m idss.train          # add --sample 40000 for a fast dev run

# 3) Run the API (from src/)
PYTHONPATH=. python3 -m uvicorn idss.api.main:app --port 8000

# 4) Run the web app (in a second terminal)
cd web && npm install && npm run dev                  # http://localhost:3000
```

## Repository structure
```
.
├── README.md
├── requirements.txt
├── data/
│   ├── README.md              # data dictionary, provenance, and the single-source rationale
│   ├── raw/                   # car_prices.csv (primary), 2016-10-dtt.xls, + unused sources
│   └── processed/             # train/val/test splits (gitignored)
├── docs/PRD.md                # product requirements document
├── src/idss/
│   ├── data/                  # dataset loading, MMR lookup, DTT benchmark, live pricing
│   ├── features/              # feature engineering (shared train/serve)
│   ├── models/                # M1 resale, M2 dts band, M3 buy/pass, registry
│   ├── decision/              # buy/pass + max-price rules
│   ├── service/               # evaluation orchestration + confidence scoring
│   └── api/                   # FastAPI app
├── web/                       # Next.js dashboard
├── models/                    # trained artifacts (gitignored)
└── .kiro/specs/used-vehicle-idss/   # requirements, design, tasks
```

## Live current-market pricing (optional)
The models train on 2014–2015 auction data, so on their own they cannot price
current-year vehicles (a post-2015 model year is flagged out-of-coverage). Set a
`MARKETCHECK_API_KEY` (see `.env.example`) to use a live market value as the resale
anchor; the provider is pluggable in `src/idss/data/live_pricing.py`.

## Documentation
- **Product spec:** `docs/PRD.md`
- **Requirements / design / tasks:** `.kiro/specs/used-vehicle-idss/`
- **Data provenance:** `data/README.md`

## Disclaimer
Decision support only — estimates value at the wholesale level from 2014–2015 auction
data. A human buyer makes the final call.
