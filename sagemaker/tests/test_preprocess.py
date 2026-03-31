from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import preprocess  # noqa: E402


def _minimal_hour_df():
    return pd.DataFrame(
        {
            "instant": range(48),
            "dteday": pd.date_range("2011-01-01", periods=2, freq="D").repeat(24).values,
            "season": [1] * 48,
            "yr": [0] * 48,
            "mnth": [1] * 48,
            "hr": list(range(24)) * 2,
            "holiday": [0] * 48,
            "weekday": [6, 0] * 24,
            "workingday": [0] * 48,
            "weathersit": [1] * 48,
            "temp": [0.3] * 48,
            "atemp": [0.3] * 48,
            "hum": [0.5] * 48,
            "windspeed": [0.1] * 48,
            "casual": [1] * 48,
            "registered": [2] * 48,
            "cnt": [10 + i for i in range(48)],
        }
    )


def test_build_training_matrices_shapes():
    df = _minimal_hour_df()
    X_train, X_test, y_train, y_test, scaler, names = preprocess.build_training_matrices(
        df, test_size_ratio=0.25
    )
    assert len(X_train) + len(X_test) == len(df)
    assert X_train.shape[1] == X_test.shape[1]
    assert scaler is not None
    assert len(names) == X_train.shape[1]


def test_build_full_training_matrix():
    df = _minimal_hour_df()
    X, y, scaler, names = preprocess.build_full_training_matrix(df)
    assert len(X) == len(df) == len(y)
    assert scaler is not None
    assert len(names) == X.shape[1]


def test_write_raw_time_splits(tmp_path):
    df = _minimal_hour_df()
    tr = tmp_path / "train.csv"
    te = tmp_path / "test.csv"
    preprocess.write_raw_time_splits(df, str(tr), str(te), test_size_ratio=0.5)
    assert tr.exists() and te.exists()
    assert len(pd.read_csv(tr)) + len(pd.read_csv(te)) == len(df)
