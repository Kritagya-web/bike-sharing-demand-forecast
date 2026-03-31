# Exact flow: what you are building

This page is the **single “goal diagram”** for this project: from **raw bike data** → **trained model** → **hosted predictions** → **scheduled daily email** with an Excel forecast. Open it in **GitHub**, **VS Code**, or **Cursor** with Mermaid preview so the drawings render.

**Companion:** [ARCHITECTURE_AND_FLOWS.md](ARCHITECTURE_AND_FLOWS.md) (full technical reference) · [README](../README.md)

---

## Your outcome in one sentence

**Train an XGBoost model on hourly bike rentals, deploy it on SageMaker, then every day automatically generate 24 hourly predictions for “tomorrow” (using a fixed weather scenario), attach an Excel report, and send it by email.**

---

## 1. Master flow (all three phases)

This diagram matches the **order you typically execute** work: prove it locally, then cloud train/deploy, then wire the daily Lambda.

```mermaid
flowchart TB
  GOAL(["Outcome: Daily email with hourly demand forecast — Excel + HTML"])

  subgraph P1["Phase 1 — Local: data + model quality"]
    direction TB
    H1["data/raw/hour.csv — UCI hourly dataset"]
    H2["pipeline.py preprocess → data/processed/train.csv, test.csv"]
    H3["pipeline.py train-local → src/train.py + preprocess.py"]
    H4["models/model.joblib — XGBoost + scaler + feature_names"]
    H5["pipeline.py evaluate — MAE / RMSE / R² on holdout"]
    H6["Optional: pipeline.py compare-models → models/compare_metrics.json"]
    H1 --> H2 --> H3 --> H4 --> H5 --> H6
  end

  subgraph P2["Phase 2 — AWS: train artifact + real-time endpoint"]
    direction TB
    S1["Training CSV on S3 — upload_data.sh or console"]
    S2[".env + config/aws_config.py — role, bucket, region"]
    S3["pipeline.py train-sagemaker → sagemaker_config.py → Training Job"]
    S4["Job runs src/train.py in SKLearn container → model.tar.gz on S3"]
    S5["deploy_endpoint.py --model-data s3://.../model.tar.gz"]
    S6["Endpoint runs inference.py — input_fn → predict_fn → output_fn"]
    S7["ENDPOINT_NAME — live JSON predictions"]
    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7
  end

  subgraph P3["Phase 3 — Automation: daily report"]
    direction TB
    L0["lambda/daily_report/hourly_profile.json — scenario weather"]
    L1["handler.py — 24 rows → endpoint → Excel → SES"]
    L2["Docker linux/amd64 → ECR → Lambda container image"]
    L3["Lambda env: ENDPOINT_NAME, REPORT_EMAIL_*, REPORT_TIMEZONE"]
    L4["EventBridge Scheduler — e.g. daily 08:00 IANA TZ"]
    L5["InvokeEndpoint → 24 preds → .xlsx + HTML → SendRawEmail"]
    L0 --> L1
    L1 --> L2 --> L3
    L4 --> L5
    L3 --> L5
  end

  H6 -.->|"Local ML OK + AWS ready"| S1
  S7 -.->|"Endpoint InService"| L3
  L5 --> GOAL
```

**How to read the dashed arrows**

- Phase 1 → Phase 2: you move on **after** local preprocess/train/evaluate look good (and AWS config is ready).
- Phase 2 → Phase 3: Lambda needs a **working endpoint** (`ENDPOINT_NAME`).

---

## 2. Phase 1 only — local ML pipeline (exact files)

```mermaid
flowchart LR
  subgraph files [On disk]
    RAW[hour.csv in data/raw]
    TRN[train.csv]
    TST[test.csv]
    JOB[model.joblib]
  end
  subgraph code [Code]
    PRE[preprocess.py]
    FIT[train.py]
    PIPE[pipeline.py]
  end
  RAW -->|preprocess| TRN
  RAW -->|preprocess| TST
  TRN -->|train-local| FIT
  PRE --- FIT
  PIPE --> RAW
  PIPE --> TRN
  FIT --> JOB
  TST -->|evaluate| JOB
```

| Step | Command | Main outputs |
|------|---------|----------------|
| 1 | `python pipeline.py preprocess` | `train.csv`, `test.csv` |
| 2 | `python pipeline.py train-local` | `models/model.joblib` |
| 3 | `python pipeline.py evaluate` | Metrics JSON printed |
| 4 | `python pipeline.py compare-models` (optional) | `models/compare_metrics.json` |

---

## 3. Phase 2 only — from laptop to SageMaker endpoint

```mermaid
flowchart TB
  subgraph you [You]
    U1["Configure role, bucket, region in .env / aws_config"]
    U2["pipeline.py train-sagemaker"]
    U3["Copy MODEL_DATA_S3 model.tar.gz from job output"]
    U4["config/deploy_endpoint --model-data S3 URI"]
  end
  subgraph aws [AWS]
    TJ[SageMaker Training Job]
    S3A[S3 model.tar.gz]
    EP[SageMaker Endpoint — SKLearn + inference.py]
  end
  U1 --> U2 --> TJ --> S3A
  U3 --> U4
  S3A --> EP
  U4 --> EP
  EP --> OUT["Save ENDPOINT_NAME for Lambda"]
```

**Artifact path:** Training packages `model.joblib` inside `model.tar.gz`. Serving loads it in `inference.py` → `model_fn`.

---

## 4. Phase 3 only — one scheduled morning run (exact call chain)

```mermaid
flowchart TB
  EB[EventBridge Scheduler cron + timezone] --> L[Lambda daily_report handler]
  L --> D{"Target date"}
  D -->|default| TMR["tomorrow in REPORT_TIMEZONE"]
  D -->|test| OVR["TARGET_DATE env YYYY-MM-DD"]
  TMR --> B["build_instances — 24 rows from hourly_profile.json"]
  OVR --> B
  B --> INV["sagemaker-runtime InvokeEndpoint JSON instances"]
  INV --> EP[SageMaker Endpoint]
  EP --> PR[24 predictions]
  PR --> XLSX["openpyxl: Counts + Chart_and_pivot"]
  PR --> HTML[HTML table + KPIs]
  XLSX --> SES[Amazon SES SendRawEmail]
  HTML --> SES
  SES --> INBOX[Recipient inbox with xlsx]
```

**Inputs to the model in this phase:** Same column names as training raw rows (`dteday`, `season`, `yr`, `mnth`, `hr`, `holiday`, `weekday`, `workingday`, `weathersit`, `temp`, `atemp`, `hum`, `windspeed`). **`instant`** may be present; preprocessing drops leakage columns consistently.

---

## 5. Prediction path inside the endpoint (exact functions)

```mermaid
flowchart LR
  REQ["HTTP JSON body instances"] --> IFn["inference.py input_fn → DataFrame"]
  IFn --> PF["predict_fn → transform_raw_for_inference → predict"]
  PF --> OF["output_fn → predictions JSON"]
  subgraph bundle [Loaded model.joblib]
    M[XGBoost]
    SC[Scaler]
    FN[feature_names]
  end
  bundle --> PF
```

---

## 6. Checklist order (copy-paste sequence)

Use this as a **literal runbook**; details are in [README](../README.md), [AWS_DAILY_REPORT.md](AWS_DAILY_REPORT.md), and [LAMBDA_DAILY_REPORT_STEP_BY_STEP.md](LAMBDA_DAILY_REPORT_STEP_BY_STEP.md).

1. Put **`hour.csv`** in `sagemaker/data/raw/`.
2. **`python pipeline.py preprocess`** → **`train-local`** → **`evaluate`**.
3. Configure AWS **`.env`** (role, bucket, region).
4. Upload training data to **S3** if needed → **`python pipeline.py train-sagemaker`**.
5. **`python deploy_endpoint.py --model-data <MODEL_DATA_S3>`** → save **`ENDPOINT_NAME`**.
6. Verify **SES** identities → optional **`python scripts/send_ses_test_email.py`**.
7. Build/push **`lambda/daily_report`** image to **ECR**; create **Lambda** with env vars.
8. Create **EventBridge** schedule → target Lambda.
9. (Optional) Regenerate **`hourly_profile.json`** after data changes: **`python scripts/generate_hourly_profile.py`**, then rebuild the Lambda image.

---

## 7. Render these diagrams offline

- **In Cursor/VS Code:** install a “Mermaid” preview extension; open this `.md` file and preview.
- **In GitHub:** push the repo; GitHub renders Mermaid in markdown.
- **For PowerPoint/Visio:** use these diagrams as the **exact blueprint**—recreate the same boxes and arrows in your tool, or export PNG from a [Mermaid Live Editor](https://mermaid.live) by pasting a diagram’s code block.

If something in your real setup differs (e.g. different bucket layout), only the **S3 paths** and **names** change—the **phase order** stays the same.
