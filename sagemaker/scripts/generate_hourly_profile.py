"""Build lambda/daily_report/hourly_profile.json median weather by hour from data/raw/hour.csv."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "raw" / "hour.csv"
OUT = ROOT / "lambda" / "daily_report" / "hourly_profile.json"


def main():
    df = pd.read_csv(CSV, parse_dates=["dteday"])
    g = df.groupby("hr").agg(
        temp=("temp", "median"),
        atemp=("atemp", "median"),
        hum=("hum", "median"),
        windspeed=("windspeed", "median"),
        weathersit=("weathersit", lambda s: int(round(s.median()))),
    )
    hours = []
    for hr in range(24):
        row = g.loc[hr]
        hours.append(
            {
                "hour": int(hr),
                "temp": float(row["temp"]),
                "atemp": float(row["atemp"]),
                "hum": float(row["hum"]),
                "windspeed": float(row["windspeed"]),
                "weathersit": int(row["weathersit"]),
            }
        )
    season_by_month = df.groupby("mnth")["season"].agg(lambda s: int(s.mode().iloc[0])).to_dict()
    season_by_month = {str(k): v for k, v in sorted(season_by_month.items())}
    payload = {"season_by_month": season_by_month, "hours": hours}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
