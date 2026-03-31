# Architecture diagrams (Visio and other sources)

This folder holds **metadata and instructions** for diagrams. The repo still contains **[Mermaid diagrams in ARCHITECTURE_AND_FLOWS.md](../ARCHITECTURE_AND_FLOWS.md)** for version control and quick previews; **Microsoft Visio** (or similar) is optional for stakeholder-ready drawings.

## Using Microsoft Visio

1. **Create** `.vsdx` files in Visio (e.g. AWS architecture, data pipeline, Lambda sequence).
2. **Share a link** (pick one):
   - **OneDrive / SharePoint:** File → Share → copy link (view or edit). Paste into `visio_links.json` as `visio_url` or `share_url`.
   - **Visio for the web:** If the diagram lives in Microsoft 365, use the browser URL to the file.
3. **Optional — files in git:** Export from Visio **PNG** or **SVG** (File → Save As) and commit under `docs/diagrams/exports/` if you want offline/preview without signing in. Avoid committing huge binary `.vsdx` unless your team wants them in LFS.

## Linking from this project

1. Copy **`visio_links.example.json`** → **`visio_links.json`** (same folder).
2. Replace placeholder URLs with your real **SharePoint / OneDrive / Visio Online** links.
3. `visio_links.json` is **gitignored** so internal links stay on your machine; commit only the **example** file, or use a public share if your policy allows.

**From the CLI** (after `visio_links.json` exists):

```bash
cd sagemaker
python pipeline.py diagram-links
```

This prints the titles and URLs so scripts or runbooks can surface them without opening the docs.

## Suggested diagram set

| Diagram | Typical Visio content |
|---------|------------------------|
| AWS end-to-end | S3, SageMaker training, endpoint, Lambda, ECR, EventBridge, SES |
| ML pipeline | Raw → preprocess → train → evaluate → artifact |
| Daily report | Lambda → profile JSON → endpoint → Excel → SES |
| IAM / security | Roles and policies (high level) |

You can mirror the sections in [ARCHITECTURE_AND_FLOWS.md](../ARCHITECTURE_AND_FLOWS.md) so Visio and Mermaid stay aligned when you update flows.
