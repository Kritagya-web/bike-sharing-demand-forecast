from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import inference  # noqa: E402
import preprocess  # noqa: E402


def test_input_fn_json():
    body = json.dumps([{"hr": 8, "temp": 0.5}])
    frame = inference.input_fn(body, "application/json")
    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == 1


def test_transform_matches_training_columns():
    base = {
        "instant": 1,
        "season": 1,
        "yr": 0,
        "mnth": 1,
        "holiday": 0,
        "weekday": 6,
        "workingday": 0,
        "weathersit": 1,
        "temp": 0.24,
        "atemp": 0.2879,
        "hum": 0.81,
        "windspeed": 0.0,
        "casual": 3,
        "registered": 13,
        "cnt": 16,
    }
    rows = []
    for i in range(20):
        r = dict(base)
        r["instant"] = i + 1
        r["hr"] = i % 24
        r["dteday"] = "2011-01-01" if i < 12 else "2011-01-02"
        r["cnt"] = 16 + i
        rows.append(r)
    df = pd.DataFrame(rows)
    df["dteday"] = pd.to_datetime(df["dteday"])
    X_train, X_test, y_train, y_test, scaler, feature_names = preprocess.build_training_matrices(
        df, test_size_ratio=0.25
    )
    infer_df = df.drop(columns=["cnt"])
    X_inf = preprocess.transform_raw_for_inference(infer_df.iloc[:1], scaler, feature_names)
    assert list(X_inf.columns) == feature_names
