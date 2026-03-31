# Bike sharing demand forecast

**Hourly bike rental demand prediction** using the UCI Bike Sharing dataset: **XGBoost** feature pipeline, optional **local** experiments, **AWS SageMaker** training and real-time inference, plus a **containerized Lambda** that sends a daily **Excel + HTML** forecast by **Amazon SES**.

## Repository layout

| Path | Purpose |
|------|---------|
| [`sagemaker/`](sagemaker/) | Main project: preprocess, train, deploy, Lambda daily report, docs |
| [`sagemaker/docs/FLOW_YOU_ARE_BUILDING.md`](sagemaker/docs/FLOW_YOU_ARE_BUILDING.md) | End-to-end flow diagrams |
| [`bike_sharing_sagemaker.ipynb`](bike_sharing_sagemaker.ipynb) | Exploratory workflow / EDA source |
| [`requirements.txt`](requirements.txt) | Root Python deps for notebooks |
| [`Readme.txt`](Readme.txt) | UCI dataset attribution |

## Quick start (SageMaker subproject)

```bash
cd sagemaker
# Copy sagemaker/.env.example to .env and set AWS variables for cloud steps.
pip install -r requirements-dev.txt   # or src/requirements.txt for minimal local ML
python pipeline.py preprocess
python pipeline.py train-local
python pipeline.py evaluate
```

Full setup, AWS deployment, and daily email: see **[sagemaker/README.md](sagemaker/README.md)**.

## License / data

Dataset terms: see **Readme.txt** (Hadi Fanaee-T, UCI / Capital Bikeshare attribution).


<div align="center">

### Show some ❤️ by starring this repository

</div>
