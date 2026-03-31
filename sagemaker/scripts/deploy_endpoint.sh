#!/usr/bin/env bash
# Deploy SageMaker real-time endpoint from model.tar.gz on S3.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/config"
: "${MODEL_DATA_S3:?Set MODEL_DATA_S3 to s3://.../model.tar.gz}"
python deploy_endpoint.py --model-data "${MODEL_DATA_S3}" "$@"
