"""SageMaker estimator setup and job submission."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

from aws_config import (
    AWS_REGION,
    S3_TRAIN_URI,
    SAGEMAKER_BUCKET,
    SAGEMAKER_ROLE_ARN,
    src_dir,
)

_CONFIG_DIR = Path(__file__).resolve().parent


def _configure_stdio_for_windows() -> None:
    """Reduce UnicodeEncodeError when SageMaker/Rich log to the console on cp1252."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def _default_training_job_name() -> str:
    """SageMaker requires a unique job name per account/region; append UTC timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"bike-demand-xgb-{ts}"


def _resolve_job_name(explicit: str | None) -> str:
    if explicit:
        return explicit
    return (os.environ.get("SAGEMAKER_TRAINING_JOB_NAME") or "").strip() or _default_training_job_name()


def _fit_stream_logs() -> bool:
    """
    Stream CloudWatch logs during fit(). On Windows (cp1252), Rich/colored logs often raise
    UnicodeEncodeError. Set SAGEMAKER_FIT_LOGS=1 and use UTF-8 console if you need live logs:
    $env:PYTHONIOENCODING='utf-8'
    """
    flag = os.environ.get("SAGEMAKER_FIT_LOGS", "").strip().lower()
    if flag in ("1", "true", "yes", "all"):
        return True
    if flag in ("0", "false", "no"):
        return False
    return sys.platform != "win32"


def load_hyperparameters() -> dict:
    path = _CONFIG_DIR / "hyperparams.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def create_sklearn_estimator(
    *,
    instance_type: str = "ml.m5.xlarge",
    framework_version: str = "1.2-1",
):
    import sagemaker
    from sagemaker.sklearn.estimator import SKLearn

    boto_sess = boto3.Session(region_name=AWS_REGION)
    session = sagemaker.Session(boto_session=boto_sess, default_bucket=SAGEMAKER_BUCKET)
    hyperparameters = load_hyperparameters()

    return SKLearn(
        entry_point="train.py",
        source_dir=str(src_dir()),
        role=SAGEMAKER_ROLE_ARN,
        instance_count=1,
        instance_type=instance_type,
        framework_version=framework_version,
        py_version="py3",
        sagemaker_session=session,
        hyperparameters=hyperparameters,
    ), session, hyperparameters


def submit_training_job(
    train_s3_uri: str | None = None,
    *,
    instance_type: str = "ml.m5.xlarge",
    job_name: str | None = None,
    local_train_file_uri: str | None = None,
):
    """
    Start a training job. Pass either train_s3_uri (default from config) or
    local_train_file_uri as file:///path (must be visible to the client launching the job).

    job_name: if omitted, uses SAGEMAKER_TRAINING_JOB_NAME or a unique name
    bike-demand-xgb-<UTC-timestamp> (required because AWS rejects duplicate job names).
    """
    _configure_stdio_for_windows()
    train_input = local_train_file_uri if local_train_file_uri else (train_s3_uri or S3_TRAIN_URI)
    resolved_name = _resolve_job_name(job_name)
    estimator, _session, _hp = create_sklearn_estimator(instance_type=instance_type)
    stream = _fit_stream_logs()
    if not stream:
        print(
            "Live CloudWatch log streaming disabled (avoids Windows console Unicode errors). "
            "Watch job in AWS Console: SageMaker -> Training -> Training jobs. "
            "To stream logs here, set SAGEMAKER_FIT_LOGS=1 and PYTHONIOENCODING=utf-8",
            file=sys.stderr,
        )
    print(f"Training job name: {resolved_name}", flush=True)
    estimator.fit({"train": train_input}, job_name=resolved_name, logs=stream)
    print(f"MODEL_DATA_S3={estimator.model_data}")
    print("Deploy endpoint: python deploy_endpoint.py --model-data " + repr(estimator.model_data))
    return estimator
