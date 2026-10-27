"""Download the January 2026 wind snapshot from Elexon into backend/data/.

Purchase decisions made in January 2026 cover delivery days 2 Jan - 1 Feb, so we pull
actuals for 1 Jan - 2 Feb and every forecast published from 30 Dec to 1 Feb.

Usage:  python -m scripts.fetch_data   (run from backend/)
"""

from __future__ import annotations

import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.elexon import fetch_wind_actuals, fetch_wind_forecasts

OUT = Path(__file__).resolve().parent.parent / "data" / "wind_jan2026.json.gz"


def main() -> None:
    actuals = fetch_wind_actuals(date(2026, 1, 1), date(2026, 2, 2))
    forecasts = fetch_wind_forecasts(
        datetime(2025, 12, 30, tzinfo=timezone.utc), datetime(2026, 2, 2, tzinfo=timezone.utc)
    )
    # Keep only forecasts targeting the analysis window, at most 48h ahead (the useful day-ahead range).
    lo, hi = "2026-01-01T00:00:00Z", "2026-02-03T00:00:00Z"
    kept = []
    for f in forecasts:
        if not (lo <= f["startTime"] < hi):
            continue
        lead_h = (
            datetime.fromisoformat(f["startTime"].replace("Z", "+00:00"))
            - datetime.fromisoformat(f["publishTime"].replace("Z", "+00:00"))
        ).total_seconds() / 3600
        if 0 <= lead_h <= 48:
            kept.append(f)

    payload = {
        "source": "Elexon BMRS FUELHH (fuelType=WIND) and WINDFOR",
        "fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actuals": actuals,
        "forecasts": kept,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    print(f"actuals={len(actuals)} forecasts={len(kept)} -> {OUT}")


if __name__ == "__main__":
    main()
