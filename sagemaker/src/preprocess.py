"""Feature pipeline aligned with bike_sharing_sagemaker.ipynb (XGBoost path)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


NUMERIC_COLS = ["temp", "hum", "windspeed"]
CAT_COLS = ["season", "yr", "holiday", "workingday", "weathersit"]
DROP_COLS = ["instant", "casual", "registered", "atemp", "dteday"]


def load_hour_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["dteday"] = pd.to_datetime(df["dteday"])
    return df


def write_raw_time_splits(
    df: pd.DataFrame,
    train_path: str,
    test_path: str,
    test_size_ratio: float = 0.2,
) -> tuple[int, int]:
    """Persist time-ordered train/test CSVs (same schema as UCI hour data, including cnt)."""
    split_index = int((1.0 - test_size_ratio) * len(df))
    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()
    for part in (train_df, test_df):
        if pd.api.types.is_datetime64_any_dtype(part["dteday"]):
            part["dteday"] = part["dteday"].dt.strftime("%Y-%m-%d")
    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)
    return len(train_df), len(test_df)


def _cyclical_and_dummies(df: pd.DataFrame, *, has_target: bool) -> tuple[pd.DataFrame, pd.Series | None]:
    """Drop leakage cols; if has_target, return y = cnt. Else cnt column is ignored if present."""
    work = df.copy()
    y = None
    if has_target:
        if "cnt" not in work.columns:
            raise ValueError("Training data must include target column 'cnt'.")
        y = work["cnt"]
        work = work.drop(columns=["cnt"])
    else:
        work = work.drop(columns=["cnt"], errors="ignore")

    work = work.drop(columns=[c for c in DROP_COLS if c in work.columns], errors="ignore")
    X = work.copy()
    X["hr_sin"] = np.sin(2 * np.pi * X["hr"] / 24)
    X["hr_cos"] = np.cos(2 * np.pi * X["hr"] / 24)
    X["mnth_sin"] = np.sin(2 * np.pi * X["mnth"] / 12)
    X["mnth_cos"] = np.cos(2 * np.pi * X["mnth"] / 12)
    X["weekday_sin"] = np.sin(2 * np.pi * X["weekday"] / 7)
    X["weekday_cos"] = np.cos(2 * np.pi * X["weekday"] / 7)
    X = X.drop(columns=["hr", "mnth", "weekday"])

    # Avoid get_dummies(..., dtype=float): that kwarg needs pandas>=1.5; base SKLearn images may ship older pandas.
    X = pd.get_dummies(X, columns=CAT_COLS, drop_first=True)
    X = X.astype(np.float64)
    return X, y


def _scale_numeric(
    X: pd.DataFrame, scaler: StandardScaler | None, fit: bool
) -> tuple[pd.DataFrame, StandardScaler]:
    if scaler is None:
        scaler = StandardScaler()
    X = X.copy()
    if fit:
        X[NUMERIC_COLS] = scaler.fit_transform(X[NUMERIC_COLS])
    else:
        X[NUMERIC_COLS] = scaler.transform(X[NUMERIC_COLS])
    return X, scaler


def _add_interaction_features(X: pd.DataFrame) -> pd.DataFrame:
    X = X.copy()
    wd = X["workingday_1"] if "workingday_1" in X.columns else 0.0
    w2 = X["weathersit_2"] if "weathersit_2" in X.columns else 0.0
    weather_dums = X[[c for c in X.columns if c.startswith("weathersit_")]]
    weather_sum = weather_dums.sum(axis=1) if not weather_dums.empty else 0.0

    X["hr_workingday"] = X["hr_sin"] * wd
    X["hr_weather_clear"] = X["hr_sin"] * w2
    X["temp_weather"] = X["temp"] * weather_sum
    X["workingday_weather"] = wd * weather_sum
    X["temp_squared"] = X["temp"] ** 2
    X["hum_squared"] = X["hum"] ** 2
    return X


def build_full_training_matrix(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, StandardScaler, list[str]]:
    """Use entire frame for fitting (e.g. after an external time split wrote train.csv only)."""
    X, y = _cyclical_and_dummies(df, has_target=True)
    assert y is not None
    X, scaler = _scale_numeric(X, None, fit=True)
    X = _add_interaction_features(X)
    feature_names = X.columns.tolist()
    return X, y, scaler, feature_names


def build_training_matrices(
    df: pd.DataFrame, test_size_ratio: float = 0.2
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, StandardScaler, list[str]]:
    """
    Time-ordered split (first (1-ratio) train, last ratio test).
    Fits StandardScaler on training numeric columns only (no test leakage).
    """
    X, y = _cyclical_and_dummies(df, has_target=True)
    assert y is not None
    split_index = int((1.0 - test_size_ratio) * len(X))
    X_train_raw, X_test_raw = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

    X_train, scaler = _scale_numeric(X_train_raw, None, fit=True)
    X_test, _ = _scale_numeric(X_test_raw, scaler, fit=False)

    X_train = _add_interaction_features(X_train)
    X_test = _add_interaction_features(X_test)

    feature_names = X_train.columns.tolist()
    X_test = X_test.reindex(columns=feature_names, fill_value=0.0)

    return X_train, X_test, y_train, y_test, scaler, feature_names


def transform_raw_for_inference(df: pd.DataFrame, scaler: StandardScaler, feature_names: list[str]) -> pd.DataFrame:
    if "dteday" in df.columns:
        df = df.copy()
        df["dteday"] = pd.to_datetime(df["dteday"])
    X, _ = _cyclical_and_dummies(df, has_target=False)
    X, _ = _scale_numeric(X, scaler, fit=False)
    X = _add_interaction_features(X)
    return X.reindex(columns=feature_names, fill_value=0.0)
