"""
SageMaker training entry point for bike demand (XGBoost, notebook-aligned features).

Environment (set by SageMaker): SM_MODEL_DIR, SM_CHANNEL_TRAIN
Local run: python train.py --train ../data/raw/hour.csv --model-dir ../models
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

from preprocess import build_full_training_matrix, build_training_matrices, load_hour_csv


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model-dir",
        type=str,
        default=os.environ.get("SM_MODEL_DIR", "./model"),
    )
    parser.add_argument(
        "--train",
        type=str,
        default=os.environ.get("SM_CHANNEL_TRAIN", "."),
    )
    parser.add_argument("--test-size-ratio", "--test_size_ratio", type=float, default=0.2)

    parser.add_argument("--n-estimators", "--n_estimators", type=int, default=700)
    parser.add_argument("--learning-rate", "--learning_rate", type=float, default=0.03)
    parser.add_argument("--max-depth", "--max_depth", type=int, default=6)
    parser.add_argument("--subsample", type=float, default=0.8)
    parser.add_argument("--colsample-bytree", "--colsample_bytree", type=float, default=0.8)
    parser.add_argument("--random-state", "--random_state", type=int, default=42)
    parser.add_argument(
        "--fit-all-rows",
        "--fit_all_rows",
        action="store_true",
        help="Fit on every row in the training CSV (use with an external train split file).",
    )

    args, unknown = parser.parse_known_args()
    if unknown:
        print("Ignoring unknown args (from container/SageMaker):", unknown, file=sys.stderr, flush=True)
    return args


def _find_training_csv(train_path: str) -> str:
    """
    SageMaker channel directory, a single CSV file, or a folder containing train.csv.
    """
    if os.path.isfile(train_path) and train_path.lower().endswith(".csv"):
        return train_path
    preferred = os.path.join(train_path, "train.csv")
    if os.path.isfile(preferred):
        return preferred
    for root, _dirs, files in os.walk(train_path):
        for f in sorted(files):
            if f.lower().endswith(".csv"):
                return os.path.join(root, f)
    raise FileNotFoundError(f"No CSV found under {train_path!r}")


def main():
    args = parse_args()
    csv_path = _find_training_csv(args.train)
    df = load_hour_csv(csv_path)

    if args.fit_all_rows:
        X_train, y_train, scaler, feature_names = build_full_training_matrix(df)
        X_test = y_test = None
    else:
        X_train, X_test, y_train, y_test, scaler, feature_names = build_training_matrices(
            df, test_size_ratio=args.test_size_ratio
        )

    model = XGBRegressor(
        n_estimators=args.n_estimators,
        learning_rate=args.learning_rate,
        max_depth=args.max_depth,
        subsample=args.subsample,
        colsample_bytree=args.colsample_bytree,
        random_state=args.random_state,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    if X_test is not None and y_test is not None:
        y_pred = model.predict(X_test)
        metrics = {
            "mae": float(mean_absolute_error(y_test, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "r2": float(r2_score(y_test, y_pred)),
        }
    else:
        metrics = {"note": "fit_all_rows; no internal holdout metrics"}
    print(json.dumps({"metrics": metrics}))

    os.makedirs(args.model_dir, exist_ok=True)
    bundle = {
        "model": model,
        "scaler": scaler,
        "feature_names": feature_names,
    }
    joblib.dump(bundle, os.path.join(args.model_dir, "model.joblib"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
