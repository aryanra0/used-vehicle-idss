# IDSS for Used Vehicle Acquisition

An Intelligent Decision Support System (IDSS) that helps used-car dealerships decide
**whether to buy a candidate vehicle and the maximum price to pay**. It predicts resale
value, a days-to-sell band, and profitability, then applies user-adjustable business
rules to produce a **Buy / Pass** recommendation with a recommended maximum purchase price.

Course project — MSE 436, Group 16.

## Repository Structure

```
.
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .gitignore
├── data/
│   ├── README.md             # Data dictionary, provenance, rejected sources
│   └── raw/                  # Blended training sources (gitignored)
│       ├── true_car_listings.csv          # Retail base (~852k, ≤2018)
│       ├── car_prices.csv                 # Wholesale + condition + MMR (~558k, ≤2015)
│       ├── used_cars.csv                  # Recency (~4k, 2013–2024)
│       └── 2016-10-dtt.xls                # Edmunds "Days To Turn" benchmark
├── docs/
│   ├── PRD.md                             # Product Requirements Document
│   ├── IDSS_Worksheet_SR_Group_16.pdf     # Original project worksheet
│   └── references/
│       └── Predicting_car_sale_time_with_data_analytics_and_machine_learning.pdf
├── src/
│   └── idss/                 # Application source (see design doc)
│       ├── data/             # Harmonization, benchmarks, market-value lookup, live pricing
│       ├── features/         # Feature engineering (shared train/serve)
│       ├── models/           # M1 resale price, M2 days-to-sell band, M3 buy/pass
│       ├── decision/         # Buy/pass + max-price rules
│       ├── service/          # Evaluation orchestration + batch
│       ├── api/              # FastAPI backend
│       └── monitoring/       # Drift, fairness, prediction logging
├── web/                      # Next.js + Tailwind dashboard (frontend)
├── tests/                    # Unit tests
├── models/                   # Trained model artifacts (gitignored)
└── .kiro/
    └── specs/used-vehicle-idss/
        ├── requirements.md   # Testable requirements (EARS)
        ├── design.md         # Architecture and design
        └── tasks.md          # Implementation plan
```

## The Three Models
| ID | Model | Task | Target |
|----|-------|------|--------|
| M1 | Resale Price | Regression | Actual sold price ($) |
| M2 | Days-to-Sell Band | Classification | Fast (≤60d) / Moderate (61–90) / Slow (91–120) / Very slow (>120) |
| M3 | Profitability / Buy-Pass | Classification | Buy or Pass, with calibrated confidence |

## Decision Logic (defaults, user-adjustable)
Recommend **Buy** only if all hold, else **Pass**:
1. Expected ROI ≥ target margin (default 15%)
2. Expected gross profit ≥ minimum (default $1,000)
3. Model confidence ≥ risk tolerance (default 0.60)

```
MaxPurchasePrice = PredictedResale − Repairs − (HoldingCostPerDay × PredictedDaysToSell) − (TargetMargin × PredictedResale)
```

## Getting Started
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Documentation
- **Product spec:** `docs/PRD.md`
- **Requirements / design / tasks:** `.kiro/specs/used-vehicle-idss/`
- **Data provenance:** `data/README.md`

## Live Current-Market Pricing (optional)
The ML model is trained on 2014–2015 auction data, so on its own it cannot price
current-year vehicles (a 2025 car falls outside its coverage and is flagged with a
warning). To get **today's** prices, connect a free live pricing feed:

1. Get a free API key from [MarketCheck](https://www.marketcheck.com/apis) (~500 calls/month).
2. Start the API with the key set:
   ```bash
   cd src
   MARKETCHECK_API_KEY=your_key PYTHONPATH=. python3 -m uvicorn idss.api.main:app --port 8000
   ```
When a key is present, the app uses the **live market value** as the resale anchor
(badge: "Live market price") and the model/benchmark become the fallback. See
`.env.example`. The provider is pluggable (`src/idss/data/live_pricing.py`) — Auto.dev
(1,000 free calls/month) can be swapped in.

## Data Note
The primary dataset (`car_prices.csv`) provides real sold prices, mileage, condition,
region, and an MMR market-value benchmark. Days-to-sell is derived from a make/segment
industry benchmark (Edmunds "Days To Turn") and is a benchmark-level estimate, not a
per-car duration. See `data/README.md` for full provenance and rejected sources.
