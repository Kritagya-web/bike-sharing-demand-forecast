"""
Deploy a SageMaker real-time endpoint from a training artifact (model.tar.gz on S3).

Prerequisite: a completed training job whose output is model.tar.gz, e.g. estimator.model_data:
  s3://bucket/prefix/model-name/output/model.tar.gz

Usage (from repo, with AWS creds and SAGEMAKER_ROLE_ARN set):
  python deploy_endpoint.py --model-data s3://your-bucket/path/output/model.tar.gz
  python deploy_endpoint.py   # uses MODEL_DATA_S3 env var

Prints endpoint name for Lambda env ENDPOINT_NAME.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_CONFIG = Path(__file__).resolve().parent
sys.path.insert(0, str(_CONFIG))

import boto3  # noqa: E402

from aws_config import AWS_REGION, SAGEMAKER_BUCKET, SAGEMAKER_ROLE_ARN, src_dir  # noqa: E402

_DEFAULT_FRAMEWORK = "1.2-1"
_DEFAULT_INSTANCE = "ml.m5.large"


def deploy(
    model_data: str,
    *,
    endpoint_name: str | None = None,
    instance_type: str = _DEFAULT_INSTANCE,
    framework_version: str = _DEFAULT_FRAMEWORK,
):
    import sagemaker
    from sagemaker.sklearn.model import SKLearnModel

    role = SAGEMAKER_ROLE_ARN
    if "YOUR_ACCOUNT" in role or "YOUR_" in role:
        raise SystemExit("Set SAGEMAKER_ROLE_ARN in environment or .env to a real SageMaker execution role.")

    boto_sess = boto3.Session(region_name=AWS_REGION)
    sm_sess = sagemaker.Session(boto_session=boto_sess, default_bucket=SAGEMAKER_BUCKET)

    model_data = model_data.strip()
    if not model_data.startswith("s3://"):
        raise SystemExit("--model-data must be an s3:// URI to model.tar.gz")

    sklearn_model = SKLearnModel(
        model_data=model_data,
        role=role,
        entry_point="inference.py",
        source_dir=str(src_dir()),
        framework_version=framework_version,
        py_version="py3",
        sagemaker_session=sm_sess,
        env={"SAGEMAKER_CONTAINER_LOG_LEVEL": "20"},
    )

    name = endpoint_name or os.environ.get(
        "SAGEMAKER_ENDPOINT_NAME",
        f"bike-demand-xgb-endpoint-{framework_version.replace('.', '-')}",
    )
    print(f"Deploying endpoint {name!r} in {AWS_REGION} with {instance_type} ...", flush=True)
    predictor = sklearn_model.deploy(
        initial_instance_count=1,
        instance_type=instance_type,
        endpoint_name=name,
    )
    ep = predictor.endpoint_name
    print(f"ENDPOINT_NAME={ep}")
    print(f"Configure Lambda env ENDPOINT_NAME={ep} (and AWS_REGION={AWS_REGION}).")
    return ep


def main():
    p = argparse.ArgumentParser(description="Deploy SKLearn inference endpoint for bike demand model")
    p.add_argument(
        "--model-data",
        default=os.environ.get("MODEL_DATA_S3", ""),
        help="s3 URI to model.tar.gz (or set MODEL_DATA_S3)",
    )
    p.add_argument("--endpoint-name", default=None)
    p.add_argument("--instance-type", default=_DEFAULT_INSTANCE)
    p.add_argument("--framework-version", default=_DEFAULT_FRAMEWORK)
    args = p.parse_args()
    if not args.model_data:
        raise SystemExit("Pass --model-data s3://.../model.tar.gz or set MODEL_DATA_S3")
    deploy(
        args.model_data,
        endpoint_name=args.endpoint_name,
        instance_type=args.instance_type,
        framework_version=args.framework_version,
    )


if __name__ == "__main__":
    main()
