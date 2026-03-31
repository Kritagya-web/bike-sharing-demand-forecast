"""AWS environment-driven settings (do not commit secrets; use .env locally)."""

from __future__ import annotations

import os
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CONFIG_DIR.parent

try:
    from dotenv import load_dotenv

    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass

AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
SAGEMAKER_BUCKET = os.environ.get("SAGEMAKER_BUCKET", os.environ.get("BUCKET_NAME", "your-training-bucket"))
SAGEMAKER_ROLE_ARN = os.environ.get(
    "SAGEMAKER_ROLE_ARN",
    "arn:aws:iam::YOUR_ACCOUNT:role/YOUR_SageMakerRole",
)

# S3 key for training data (upload with scripts/upload_data.sh)
S3_TRAIN_PREFIX = os.environ.get("S3_TRAIN_PREFIX", "bike-sharing/hour.csv")
S3_TRAIN_URI = f"s3://{SAGEMAKER_BUCKET}/{S3_TRAIN_PREFIX}"


def raw_data_dir() -> Path:
    return _PROJECT_ROOT / "data" / "raw"


def processed_data_dir() -> Path:
    return _PROJECT_ROOT / "data" / "processed"


def models_dir() -> Path:
    return _PROJECT_ROOT / "models"


def src_dir() -> Path:
    return _PROJECT_ROOT / "src"
