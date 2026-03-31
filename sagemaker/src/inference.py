"""
SageMaker serving entry point for the bundled sklearn/XGBoost + preprocess pipeline.
"""

from __future__ import annotations

import io
import json
import os

import joblib
import pandas as pd

from preprocess import transform_raw_for_inference


def model_fn(model_dir: str):
    path = os.path.join(model_dir, "model.joblib")
    return joblib.load(path)


def input_fn(request_body: str | bytes, content_type: str):
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    content_type = (content_type or "text/csv").lower()
    if content_type == "application/json":
        payload = json.loads(request_body)
        if isinstance(payload, dict) and "instances" in payload:
            rows = payload["instances"]
        else:
            rows = payload
        frame = pd.DataFrame(rows)
    elif "csv" in content_type:
        frame = pd.read_csv(io.StringIO(request_body), parse_dates=["dteday"])
    else:
        raise ValueError(f"Unsupported content type: {content_type}")

    if "dteday" in frame.columns and not pd.api.types.is_datetime64_any_dtype(frame["dteday"]):
        frame = frame.copy()
        frame["dteday"] = pd.to_datetime(frame["dteday"])
    return frame


def predict_fn(input_data: pd.DataFrame, model_bundle: dict):
    scaler = model_bundle["scaler"]
    feature_names = model_bundle["feature_names"]
    clf = model_bundle["model"]
    X = transform_raw_for_inference(input_data, scaler, feature_names)
    preds = clf.predict(X)
    return preds.tolist()


def output_fn(prediction, accept: str | None = None):
    accept = (accept or "application/json").lower()
    if "json" in accept:
        body = json.dumps({"predictions": prediction})
        return body, "application/json"
    raise ValueError(f"Unsupported accept type: {accept}")
