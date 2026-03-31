"""One-off helper to sync notebooks from bike_sharing_sagemaker.ipynb; run from repo root."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
NB_SRC = REPO / "bike_sharing_sagemaker.ipynb"


def eda_notebook():
    nb = json.loads(NB_SRC.read_text(encoding="utf-8"))
    out_cells = []
    for i, c in enumerate(nb["cells"]):
        if i > 37:
            break
        ct = c["cell_type"]
        src = "".join(c.get("source", []))
        if ct == "markdown":
            out_cells.append({"cell_type": "markdown", "metadata": {}, "source": c["source"]})
            continue
        if ct != "code":
            continue
        s = src.strip()
        if not s:
            continue
        if s.startswith("df = hour_df.copy()") or s.startswith("df = df.drop"):
            break
        if s.startswith("y = df["):
            break
        src2 = src.replace(
            "pd.read_csv('hour.csv')",
            'pd.read_csv("../data/raw/hour.csv", parse_dates=["dteday"])',
        )
        src2 = src2.replace(
            'pd.read_csv("hour.csv")',
            'pd.read_csv("../data/raw/hour.csv", parse_dates=["dteday"])',
        )
        lines = src2.splitlines()
        out_cells.append(
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [ln + "\n" for ln in lines[:-1]] + ([lines[-1]] if lines else []),
            }
        )

    for cell in out_cells:
        if cell["cell_type"] != "code":
            continue
        txt = "".join(cell["source"])
        if "../data/raw/hour.csv" in txt and "parse_dates" not in txt:
            cell["source"] = [
                t.replace(
                    'pd.read_csv("../data/raw/hour.csv")',
                    'pd.read_csv("../data/raw/hour.csv", parse_dates=["dteday"])',
                )
                for t in cell["source"]
            ]

    intro = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# 01 — EDA (from `bike_sharing_sagemaker.ipynb`)\n",
            "\n",
            "Uses `../data/raw/hour.csv`. Install dev deps: `pip install -r ../requirements-dev.txt`.\n",
        ],
    }
    full = {
        "cells": [intro] + out_cells,
        "metadata": dict(nb.get("metadata", {})),
        "nbformat": nb["nbformat"],
        "nbformat_minor": nb["nbformat_minor"],
    }
    full["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    outp = ROOT / "notebooks" / "01_eda.ipynb"
    outp.write_text(json.dumps(full, indent=1), encoding="utf-8")
    print("Wrote", outp, "cells", len(full["cells"]))


def preprocessing_notebook():
    nb = json.loads(NB_SRC.read_text(encoding="utf-8"))
    cells_out = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# 02 — Preprocessing & categorical analysis\n",
                "\n",
                "Mirrors preprocessing + Cramér's V section from the main notebook.\n",
            ],
        }
    ]
    for idx in (31, 32, 33, 34):
        c = nb["cells"][idx]
        if c["cell_type"] == "code":
            src = "".join(c["source"])
            src = src.replace("hour_df", "hour")
            preamble = (
                "import pandas as pd\n"
                "import numpy as np\n"
                "import matplotlib.pyplot as plt\n"
                "import seaborn as sns\n\n"
                'hour = pd.read_csv("../data/raw/hour.csv", parse_dates=["dteday"])\n\n'
            )
            if idx == 31:
                src = preamble + src
            lines = src.splitlines()
            cells_out.append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [ln + "\n" for ln in lines[:-1]] + ([lines[-1]] if lines else []),
                }
            )
    full = {
        "cells": cells_out,
        "metadata": dict(nb.get("metadata", {})),
        "nbformat": nb["nbformat"],
        "nbformat_minor": nb["nbformat_minor"],
    }
    full["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    outp = ROOT / "notebooks" / "02_preprocessing.ipynb"
    outp.write_text(json.dumps(full, indent=1), encoding="utf-8")
    print("Wrote", outp)


if __name__ == "__main__":
    eda_notebook()
    preprocessing_notebook()
