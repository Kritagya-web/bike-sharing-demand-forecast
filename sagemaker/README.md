# Bike rental — SageMaker layout

Project structure mirrors the standard SageMaker workflow: raw/processed data, notebooks, `src` training and inference code, config, tests, and shell helpers.

## Layout

- `data/raw/` — `hour.csv`, `day.csv` (UCI Bike Sharing)
- `data/processed/` — time-based `train.csv` / `test.csv` from `pipeline.py preprocess`
- `notebooks/` — EDA, preprocessing notes, SageMaker launch examples
- `src/` — `preprocess.py`, `train.py`, `inference.py`, `requirements.txt`
- `models/` — local artifacts (`model.joblib`, `xgb_bike_model.pkl` after local training)
- `config/` — `hyperparams.json`, `aws_config.py`, `sagemaker_config.py`, `deploy_endpoint.py`
- `lambda/daily_report/` — containerized Lambda: hourly forecast Excel + chart, email via SES (see `docs/AWS_DAILY_REPORT.md`)
- `docs/` — **[Exact flow you are building](docs/FLOW_YOU_ARE_BUILDING.md)** (master diagram), **[Architecture & flow diagrams](docs/ARCHITECTURE_AND_FLOWS.md)** (Mermaid), **[Visio / share links](docs/diagrams/README.md)** (`visio_links.json` + `python pipeline.py diagram-links`), AWS deployment, EventBridge scheduling
- `tests/` — `pytest` for preprocess and inference helpers
- `scripts/` — `upload_data.sh`, `run_training_job.sh`, `deploy_endpoint.sh`, `generate_hourly_profile.py`, `send_ses_test_email.py`, `ses_diagnose.py`
- `pipeline.py` — `preprocess` → `train-local` → `train-sagemaker`

## Setup

1. Copy `hour.csv` / `day.csv` into `data/raw/` (or run from repo root copies).
2. Copy `.env.example` to `.env` and set AWS and bucket variables (never commit `.env`).
3. **Training / inference (minimal):** `pip install -r src/requirements.txt`
4. **Notebooks + EDA + model comparison:** `pip install -r requirements-dev.txt` (adds matplotlib, seaborn, scipy, pytest).
5. For cloud jobs: `pip install -r requirements-aws.txt` (pins **SageMaker SDK 2.x**; v3 removed `sagemaker.sklearn.estimator.SKLearn` used by this repo).

## Commands

```bash
python pipeline.py preprocess
python pipeline.py compare-models  # LR, RF, RF tuned, XGB — same features as production train.py; writes models/compare_metrics.json
python pipeline.py train-local   # uses data/processed/train.csv when present (fits all rows)
python pipeline.py evaluate   # scores data/processed/test.csv (run after preprocess + train-local)
# After S3 upload and valid role/bucket:
python pipeline.py train-sagemaker
# Optional fixed name (must be new each run on AWS): python pipeline.py train-sagemaker --job-name my-run-1
# Architecture diagram URLs (after copying docs/diagrams/visio_links.example.json → visio_links.json):
python pipeline.py diagram-links
```

**Windows:** live log streaming during `train-sagemaker` is **off by default** (the SageMaker SDK’s colored CloudWatch output can crash with `UnicodeEncodeError` on cp1252). The job still runs and blocks until it finishes. Watch progress in **SageMaker console → Training jobs**. To stream logs in PowerShell: `$env:PYTHONIOENCODING='utf-8'; $env:SAGEMAKER_FIT_LOGS='1'` then run the pipeline again.

For a single-file experiment you can delete `data/processed/*.csv` and keep `data/raw/hour.csv`; `train-local` will then do an internal 80/20 split and print metrics.

**Notebooks** `notebooks/01_eda.ipynb` and `02_preprocessing.ipynb` are synced from `bike_sharing_sagemaker.ipynb` (EDA plots + Cramér’s V / categorical importance). Re-run `python _build_notebooks.py` from the `sagemaker/` folder only if you regenerate them from the source notebook after edits.

SageMaker training uses `sagemaker.sklearn.estimator.SKLearn` with `source_dir=src/`, `entry_point=train.py`, and `requirements.txt` for XGBoost.

## Deploy endpoint and daily 8:00 email report (AWS)

**Beginner walkthrough (Lambda + Docker + ECR + schedule):** **[docs/LAMBDA_DAILY_REPORT_STEP_BY_STEP.md](docs/LAMBDA_DAILY_REPORT_STEP_BY_STEP.md)**  

Shorter reference: **[docs/AWS_DAILY_REPORT.md](docs/AWS_DAILY_REPORT.md)** (train → deploy → SES → Lambda image → EventBridge Scheduler).

**Short checklist**

1. **Train** on AWS; copy `MODEL_DATA_S3` printed at the end of `pipeline.py train-sagemaker` (or `submit_training_job`).
2. **Deploy endpoint:** `cd config && python deploy_endpoint.py --model-data s3://.../model.tar.gz` (or `scripts/deploy_endpoint.sh` with `MODEL_DATA_S3` set). Save `ENDPOINT_NAME`.
3. **SES:** Verify sender and (in sandbox) recipient — see **§3 in [docs/AWS_DAILY_REPORT.md](docs/AWS_DAILY_REPORT.md)**. Quick test: `python scripts/send_ses_test_email.py` from `sagemaker/` with `REPORT_EMAIL_FROM` / `REPORT_EMAIL_TO` in `.env`.
4. **Lambda IAM:** Allow `sagemaker:InvokeEndpoint` on that endpoint and `ses:SendRawEmail` from your verified from-address. See policy snippet in `docs/AWS_DAILY_REPORT.md`.
5. **Build/push** `lambda/daily_report` Docker image to ECR; create Lambda with env vars `ENDPOINT_NAME`, `REPORT_EMAIL_FROM`, `REPORT_EMAIL_TO`, `REPORT_TIMEZONE` (e.g. `America/New_York`).
6. **Schedule:** EventBridge Scheduler, daily `cron(0 8 * * ? *)` with timezone `America/New_York`, target = Lambda.

**Weather scenario:** Predictions use median-by-hour fields in `lambda/daily_report/hourly_profile.json`. Regenerate with `python scripts/generate_hourly_profile.py` after updating `data/raw/hour.csv`.

## Tests

```bash
pytest tests/
```
