"""M1 — Resale price regression.

Gradient-boosted trees on a log-transformed target (sold price is right-skewed),
inverted on output so errors are reported on the dollar scale.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline

from ..features.engineering import build_features
from .preprocessing import build_preprocessor


class ResalePriceModel:
    """Predicts expected resale (sold) price in dollars."""

    def __init__(self, random_state: int = 42):
        base = Pipeline(
            steps=[
                ("pre", build_preprocessor()),
                (
                    "gb",
                    HistGradientBoostingRegressor(
                        max_iter=300,
                        learning_rate=0.08,
                        max_depth=None,
                        random_state=random_state,
                    ),
                ),
            ]
        )
        # Log-transform the skewed price target; invert on predict.
        self.model = TransformedTargetRegressor(
            regressor=base, func=np.log1p, inverse_func=np.expm1
        )

    def fit(self, df: pd.DataFrame) -> "ResalePriceModel":
        X = build_features(df)
        y = df["price"].astype(float).values
        self.model.fit(X, y)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        X = build_features(df)
        return np.clip(self.model.predict(X), 0, None)
