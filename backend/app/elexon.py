"""Thin client for the two Elexon BMRS datasets we use (FUELHH actuals, WINDFOR forecasts)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"


def _get(client: httpx.Client, path: str, params: dict) -> list[dict]:
    resp = client.get(f"{BASE}/{path}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_wind_actuals(start: date, end: date) -> list[dict]:
    """Half-hourly national wind generation (MW) for settlement dates start..end inclusive."""
    rows: list[dict] = []
    with httpx.Client() as client:
        day = start
        while day <= end:
            chunk_end = min(day + timedelta(days=6), end)
            data = _get(
                client,
                "FUELHH/stream",
                {"settlementDateFrom": day.isoformat(), "settlementDateTo": chunk_end.isoformat(), "fuelType": "WIND"},
            )
            rows += [
                {"startTime": r["startTime"], "generation": r["generation"]}
                for r in data
                if r.get("fuelType") == "WIND"
            ]
            day = chunk_end + timedelta(days=1)
    return rows


def fetch_wind_forecasts(publish_from: datetime, publish_to: datetime) -> list[dict]:
    """Every WINDFOR forecast vintage published in [publish_from, publish_to)."""
    rows: list[dict] = []
    with httpx.Client() as client:
        cursor = publish_from
        while cursor < publish_to:
            nxt = min(cursor + timedelta(days=1), publish_to)
            data = _get(
                client,
                "WINDFOR/stream",
                {
                    "publishDateTimeFrom": cursor.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "publishDateTimeTo": nxt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            rows += [
                {"publishTime": r["publishTime"], "startTime": r["startTime"], "generation": r["generation"]}
                for r in data
            ]
            cursor = nxt
    return rows
