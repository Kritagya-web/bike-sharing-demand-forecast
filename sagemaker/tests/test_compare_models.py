from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from compare_models import run_compare  # noqa: E402


def test_compare_models_produces_four_rows():
    hour = ROOT / "data" / "raw" / "hour.csv"
    if not hour.exists():
        pytest.skip("hour.csv not in data/raw")
    out = run_compare(str(hour), test_size_ratio=0.2, output_json=None)
    assert len(out) == 4
    assert set(out["Model"]) == {
        "LinearRegression",
        "RandomForest (default)",
        "RandomForest (tuned)",
        "XGBoost",
    }
    assert out["r2"].notna().all()
