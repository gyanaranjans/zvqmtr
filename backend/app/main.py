from __future__ import annotations

import gzip
import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analytics import WindData, accuracy_report, day_view

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "wind_jan2026.json.gz"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# Purchase decisions made in January 2026 (D-1 = 1..31 Jan) -> delivery days 2 Jan .. 1 Feb.
FIRST_DAY, LAST_DAY = date(2026, 1, 2), date(2026, 2, 1)
DELIVERY_DAYS = [FIRST_DAY + timedelta(days=i) for i in range((LAST_DAY - FIRST_DAY).days + 1)]

app = FastAPI(title="UK wind forecast desk", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@lru_cache(maxsize=1)
def load_data() -> WindData:
    with gzip.open(DATA_FILE, "rt", encoding="utf-8") as fh:
        return WindData.from_payload(json.load(fh))


@lru_cache(maxsize=24)
def cached_report(decision_hour: int) -> dict:
    return accuracy_report(load_data(), DELIVERY_DAYS, decision_hour)


def check_hour(h: int) -> int:
    if not 0 <= h <= 23:
        raise HTTPException(422, "decision_hour must be 0-23")
    return h


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/meta")
def meta() -> dict:
    data = load_data()
    return {
        "first_day": FIRST_DAY.isoformat(),
        "last_day": LAST_DAY.isoformat(),
        "default_decision_hour": 10,
        "fetched_at": data.fetched_at,
        "n_actuals": len(data.actuals),
        "n_forecast_points": sum(len(v) for v in data.forecasts.values()),
        "source": "Elexon BMRS: FUELHH (fuelType=WIND) actuals, WINDFOR forecasts",
    }


@app.get("/api/day")
def day(date_: date = Query(..., alias="date"), decision_hour: int = 10) -> dict:
    check_hour(decision_hour)
    if not FIRST_DAY <= date_ <= LAST_DAY:
        raise HTTPException(422, f"date must be between {FIRST_DAY} and {LAST_DAY}")
    o = cached_report(decision_hour)["overall"]
    return day_view(load_data(), date_, decision_hour, (o["p10"], o["p90"]))


@app.get("/api/accuracy")
def accuracy(decision_hour: int = 10) -> dict:
    return cached_report(check_hour(decision_hour))


# In Docker the built React app is copied to backend/static and served from the same origin.
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        target = STATIC_DIR / path
        return FileResponse(target if target.is_file() else STATIC_DIR / "index.html")
