"""
Train baseline Linear Regression, Random Forest (default + tuned), and XGBoost on the same
feature matrix as `train.py`, then print a metrics comparison (notebook parity).

Not used as the SageMaker training entry point; run locally or from `pipeline.py compare-models`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

from preprocess import build_training_matrices, load_hour_csv


def _metrics(y_true, y_pred) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }


def run_compare(
    csv_path: str,
    test_size_ratio: float = 0.2,
    *,
    output_json: str | None = None,
) -> pd.DataFrame:
    df = load_hour_csv(csv_path)
    X_train, X_test, y_train, y_test = build_training_matrices(df, test_size_ratio=test_size_ratio)[:4]

    rows: list[dict] = []

    lr = LinearRegression()
    lr.fit(X_train, y_train)
    pred = lr.predict(X_test)
    m = _metrics(y_test, pred)
    rows.append({"Model": "LinearRegression", **m})

    rf = RandomForestRegressor(
        n_estimators=200,
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    pred = rf.predict(X_test)
    rows.append({"Model": "RandomForest (default)", **_metrics(y_test, pred)})

    rf_tuned = RandomForestRegressor(
        n_estimators=300,
        max_depth=15,
        min_samples_split=10,
        min_samples_leaf=5,
        max_features="sqrt",
        random_state=42,
        n_jobs=-1,
    )
    rf_tuned.fit(X_train, y_train)
    pred = rf_tuned.predict(X_test)
    rows.append({"Model": "RandomForest (tuned)", **_metrics(y_test, pred)})

    xgb = XGBRegressor(
        n_estimators=700,
        learning_rate=0.03,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    xgb.fit(X_train, y_train)
    pred = xgb.predict(X_test)
    rows.append({"Model": "XGBoost", **_metrics(y_test, pred)})

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    if output_json:
        os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
        Path(output_json).write_text(out.to_json(orient="records", indent=2), encoding="utf-8")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default=None, help="Path to hour.csv (default: ../data/raw/hour.csv)")
    parser.add_argument("--test-size-ratio", "--test_size_ratio", type=float, default=0.2)
    parser.add_argument("--output-json", type=str, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    csv_path = args.data or str(root / "data" / "raw" / "hour.csv")
    if not os.path.isfile(csv_path):
        print(f"No data at {csv_path}", file=sys.stderr)
        sys.exit(1)

    run_compare(csv_path, test_size_ratio=args.test_size_ratio, output_json=args.output_json)


if __name__ == "__main__":
    main()
