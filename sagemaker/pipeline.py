"""
Orchestrate: preprocess (raw splits) → local train → evaluate (holdout) → optional SageMaker train.

Usage:
  python pipeline.py preprocess
  python pipeline.py train-local
  python pipeline.py evaluate
  python pipeline.py train-sagemaker
  python pipeline.py compare-models
  python pipeline.py diagram-links   # prints Visio/share URLs from docs/diagrams/visio_links.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"

sys.path.insert(0, str(SRC))


def step_preprocess(test_size_ratio: float = 0.2) -> None:
    from preprocess import load_hour_csv, write_raw_time_splits

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    hour = DATA_RAW / "hour.csv"
    if not hour.exists():
        raise FileNotFoundError(f"Missing {hour}. Copy UCI hour.csv into data/raw/.")
    df = load_hour_csv(str(hour))
    n_tr, n_te = write_raw_time_splits(
        df,
        str(DATA_PROCESSED / "train.csv"),
        str(DATA_PROCESSED / "test.csv"),
        test_size_ratio=test_size_ratio,
    )
    print(json.dumps({"preprocess": {"train_rows": n_tr, "test_rows": n_te}}))


def step_train_local() -> None:
    MODELS.mkdir(parents=True, exist_ok=True)
    processed_train = DATA_PROCESSED / "train.csv"
    if processed_train.exists():
        train_csv = processed_train
        extra = ["--fit-all-rows"]
    else:
        train_csv = DATA_RAW / "hour.csv"
        if not train_csv.exists():
            raise FileNotFoundError(f"Missing {train_csv}. Add data or run: python pipeline.py preprocess")
        extra = []
    cmd = [
        sys.executable,
        str(SRC / "train.py"),
        "--train",
        str(train_csv),
        "--model-dir",
        str(MODELS),
        *extra,
    ]
    subprocess.run(cmd, check=True, cwd=str(SRC))
    # Also save legacy name for local workflows
    import shutil

    artifact = MODELS / "model.joblib"
    legacy = MODELS / "xgb_bike_model.pkl"
    if artifact.exists():
        shutil.copy2(artifact, legacy)
    print(json.dumps({"train_local": {"model_dir": str(MODELS), "artifact": str(artifact)}}))


def step_evaluate() -> None:
    import json as json_lib

    import joblib
    import numpy as np
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    from preprocess import load_hour_csv, transform_raw_for_inference

    artifact = MODELS / "model.joblib"
    test_csv = DATA_PROCESSED / "test.csv"
    if not artifact.exists():
        raise FileNotFoundError(f"Train locally first; missing {artifact}")
    if not test_csv.exists():
        raise FileNotFoundError(f"Run preprocess first; missing {test_csv}")

    bundle = joblib.load(artifact)
    df = load_hour_csv(str(test_csv))
    y = df["cnt"].values
    X_raw = df.drop(columns=["cnt"])
    X = transform_raw_for_inference(X_raw, bundle["scaler"], bundle["feature_names"])
    pred = bundle["model"].predict(X)
    metrics = {
        "mae": float(mean_absolute_error(y, pred)),
        "rmse": float(np.sqrt(mean_squared_error(y, pred))),
        "r2": float(r2_score(y, pred)),
    }
    print(json_lib.dumps({"evaluate": metrics}))


def step_train_sagemaker(job_name: str | None = None) -> None:
    cfg = ROOT / "config"
    sys.path.insert(0, str(cfg))
    from sagemaker_config import submit_training_job  # noqa: E402

    submit_training_job(job_name=job_name)


def step_diagram_links() -> None:
    """Print architecture diagram URLs from docs/diagrams/visio_links.json if present."""
    path = ROOT / "docs" / "diagrams" / "visio_links.json"
    example = ROOT / "docs" / "diagrams" / "visio_links.example.json"
    if not path.is_file():
        print(
            json.dumps(
                {
                    "diagram_links": None,
                    "message": f"Create {path.name} by copying {example.name} "
                    f"(see docs/diagrams/README.md).",
                    "example_path": str(example),
                },
                indent=2,
            )
        )
        return
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        diagrams = data
        updated_meta = None
    elif isinstance(data, dict):
        updated_meta = data.get("updated")
        diagrams = data.get("diagrams")
        if not diagrams and ("title" in data or "visio_url" in data or "share_url" in data):
            diagrams = [data]
        elif diagrams is None:
            diagrams = []
    else:
        diagrams = []
        updated_meta = None
    out = {
        "diagram_links": {
            "updated": updated_meta,
            "items": [],
        },
    }
    for d in diagrams:
        if not isinstance(d, dict):
            continue
        item = {
            "id": d.get("id"),
            "title": d.get("title"),
            "visio_url": d.get("visio_url") or d.get("share_url"),
            "export_png_relative": d.get("export_png_relative"),
            "description": d.get("description"),
        }
        out["diagram_links"]["items"].append({k: v for k, v in item.items() if v})
    print(json.dumps(out, indent=2))


def step_compare_models(test_size_ratio: float) -> None:
    hour = DATA_RAW / "hour.csv"
    if not hour.exists():
        raise FileNotFoundError(f"Missing {hour}. Copy hour.csv into data/raw/.")
    cmd = [
        sys.executable,
        str(SRC / "compare_models.py"),
        "--data",
        str(hour),
        "--test-size-ratio",
        str(test_size_ratio),
        "--output-json",
        str(MODELS / "compare_metrics.json"),
    ]
    MODELS.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True, cwd=str(SRC))


def main():
    p = argparse.ArgumentParser(description="Bike rental SageMaker pipeline")
    p.add_argument(
        "command",
        choices=[
            "preprocess",
            "train-local",
            "evaluate",
            "compare-models",
            "train-sagemaker",
            "diagram-links",
        ],
        help="Pipeline step",
    )
    p.add_argument("--test-size-ratio", type=float, default=0.2)
    p.add_argument(
        "--job-name",
        default=None,
        help="For train-sagemaker only: SageMaker training job name (default: unique timestamped name).",
    )
    args = p.parse_args()

    if args.command == "preprocess":
        step_preprocess(test_size_ratio=args.test_size_ratio)
    elif args.command == "train-local":
        step_train_local()
    elif args.command == "evaluate":
        sys.path.insert(0, str(SRC))
        step_evaluate()
    elif args.command == "compare-models":
        step_compare_models(test_size_ratio=args.test_size_ratio)
    elif args.command == "train-sagemaker":
        step_train_sagemaker(job_name=args.job_name)
    elif args.command == "diagram-links":
        step_diagram_links()


if __name__ == "__main__":
    main()
