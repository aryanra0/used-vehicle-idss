"""FastAPI backend for the Used Vehicle Acquisition IDSS.

Run from the src/ directory (or with PYTHONPATH=src):

    uvicorn idss.api.main:app --reload --port 8000
"""

from __future__ import annotations

import io
import json
from functools import lru_cache
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .. import config
from ..service import batch as batch_mod
from ..service.evaluation import EvaluationService
from ..service.types import Assumptions, VehicleInput

app = FastAPI(title="Used Vehicle IDSS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    # Allow the local dev web app on any port (Next may fall back to 3001, etc.).
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_service() -> EvaluationService:
    return EvaluationService()


# --- request models ------------------------------------------------------
class AssumptionsIn(BaseModel):
    target_profit_margin: float = 0.15
    min_dollar_profit: float = 1000.0
    risk_tolerance: float = 0.60
    holding_cost_per_day: float = 20.0
    holding_period_days: int = 45
    repair_estimate: float = 0.0
    acquisition_discount: float = 0.20


class VehicleIn(BaseModel):
    year: int
    make: str
    model: str
    odometer: float
    condition: float
    body: str = ""
    transmission: str = ""
    trim: str = ""
    color: str = ""
    interior: str = ""
    state: str = ""
    mmr: Optional[float] = None
    listing_price: Optional[float] = None


class EvaluateRequest(BaseModel):
    vehicle: VehicleIn
    assumptions: AssumptionsIn = Field(default_factory=AssumptionsIn)


# --- endpoints -----------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/options")
def options() -> dict:
    path = config.MODELS_DIR / "options.json"
    if not path.exists():
        raise HTTPException(500, "options.json not found; run training / option build.")
    return json.loads(path.read_text())


@app.get("/metadata")
def metadata() -> dict:
    from ..models import registry

    return {
        "defaults": AssumptionsIn().model_dump(),
        "dts_bands": {"edges": config.DTS_BAND_EDGES, "labels": config.DTS_BAND_LABELS},
        "models": {
            name: registry.load_metadata(name).get("metrics", {})
            for name in ("m1_resale", "m2_dts_band", "m3_buy_pass")
        },
    }


@app.post("/evaluate")
def evaluate(req: EvaluateRequest) -> dict:
    svc = get_service()
    vehicle = VehicleInput(**req.vehicle.model_dump())
    assumptions = Assumptions(**req.assumptions.model_dump())
    try:
        result = svc.evaluate(vehicle, assumptions)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Evaluation failed: {exc}") from exc
    return result.to_dict()


@app.post("/evaluate-batch")
async def evaluate_batch(
    file: UploadFile = File(...),
    target_profit_margin: float = 0.15,
    min_dollar_profit: float = 1000.0,
    risk_tolerance: float = 0.60,
    holding_cost_per_day: float = 20.0,
    holding_period_days: int = 45,
    repair_estimate: float = 0.0,
    acquisition_discount: float = 0.20,
    objective: str = "profit",
) -> dict:
    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not parse CSV: {exc}") from exc

    assumptions = Assumptions(
        target_profit_margin=target_profit_margin,
        min_dollar_profit=min_dollar_profit,
        risk_tolerance=risk_tolerance,
        holding_cost_per_day=holding_cost_per_day,
        holding_period_days=holding_period_days,
        repair_estimate=repair_estimate,
        acquisition_discount=acquisition_discount,
    )
    svc = get_service()
    results, errors = batch_mod.evaluate_csv(df, svc, assumptions)
    ranked = batch_mod.rank_results(results, objective)
    return {
        "results": ranked.to_dict("records"),
        "errors": errors.to_dict("records"),
        "summary": {
            "evaluated": int(len(ranked)),
            "errors": int(len(errors)),
            "buy": int((ranked["recommendation"] == "Buy").sum()) if len(ranked) else 0,
        },
    }
