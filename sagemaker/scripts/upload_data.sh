#!/usr/bin/env bash
# Upload raw hour data to S3 for SageMaker training.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
: "${AWS_REGION:?Set AWS_REGION}"
: "${SAGEMAKER_BUCKET:?Set SAGEMAKER_BUCKET}"
: "${S3_TRAIN_PREFIX:=bike-sharing/hour.csv}"
aws s3 cp "${ROOT}/data/raw/hour.csv" "s3://${SAGEMAKER_BUCKET}/${S3_TRAIN_PREFIX}"
echo "Uploaded to s3://${SAGEMAKER_BUCKET}/${S3_TRAIN_PREFIX}"
