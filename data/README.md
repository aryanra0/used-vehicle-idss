# Data

Provenance and dictionary for the datasets used by the IDSS. Raw data files are
**gitignored** (they are large); this document records what they are and where they came from.

The price models train on a **blend of three real sources** (see `src/idss/data/harmonize.py`),
harmonized to a common schema with a `source_channel` flag (wholesale vs retail).

## 1. Retail base — `raw/true_car_listings.csv`
- ~852,000 real US retail listings; model years ≤2018. Largest, cleanest source.
- Columns: Price (asking), Year, Mileage, City, State, VIN, Make, Model.
- Role: primary base for **M1 (resale price)**. `source_channel = retail`.
- Note: transmission is smushed onto `Model` (e.g., "ILX6-Speed") and is stripped during harmonization.

## 2. Wholesale + condition + MMR — `raw/car_prices.csv`
- ~558,000 real wholesale/auction records, ~2014–2015. Public "Vehicle Sales Data" (Kaggle).
- Columns include: year, make, model, trim, body, transmission, vin, state, **condition**, odometer,
  color, interior, seller, **mmr**, **sellingprice** (mapped to `price`), saledate.
- Role: contributes real sold prices, the only **condition** signal, and a real **MMR** benchmark.
  `source_channel = wholesale`.

## 3. Recency — `raw/used_cars.csv`
- ~4,000 real US retail records reaching **2013–2024**.
- Columns: brand, model, model_year, milage, fuel_type, engine, transmission, ext/int color,
  accident, clean_title, price.
- Role: recent (2019+) coverage. `source_channel = retail`.

## Days-to-Sell Benchmark — `raw/2016-10-dtt.xls`
- Edmunds "Days To Turn": monthly average days-to-sell by manufacturer/make/segment (Oct 2015–Oct 2016).
- Role: joined by make to derive the **M2 days-to-sell band** (Fast ≤60, Moderate 61–90, Slow 91–120, Very slow >120; calibrated to the observed ~40–105 day spread, median ~71).
- Caveat: aggregate (not per-car), different period → treated as an approximate benchmark.

## Harmonized schema (after `harmonize.load_blended()`)
`price, year, mileage, make, model, state, condition (nullable), source_channel, source`

## Market value
Real `mmr` exists only for the wholesale source; elsewhere a **group-median-price proxy**
(by make/model/year, retail-biased) stands in, computed in `mmr_lookup.py`.

## Rejected / removed sources
- `car_sales_data.csv` (+ duplicates) — **synthetic**: 5 makes × 5 models randomly paired
  ("Nissan F-150"), no real signal.
- `car-price-prediction` / Georgian `train.csv`/`test.csv` — different schema (Levy, Airbags), not used.
- Moroccan used-cars dataset — wrong market and currency.
- `car_sales_demographics.csv` — buyer demographics only; not useful for pricing.
All removed during cleanup.

## Future
- Live current-market prices via MarketCheck/Auto.dev API (the only path to true "today" pricing).
- A per-car listing/entry date would enable a real per-vehicle days-to-sell model.
