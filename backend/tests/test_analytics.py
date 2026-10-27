from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.analytics import WindData, decision_cutoff, quantile, summarize
from app.main import app


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_decision_cutoff_is_previous_day_local():
    assert decision_cutoff(date(2026, 1, 10), 10) == ts("2026-01-09T10:00:00")


def test_forecast_at_picks_latest_vintage_not_after_cutoff():
    data = WindData.from_payload(
        {
            "actuals": [],
            "forecasts": [
                {"publishTime": "2026-01-09T07:30:00Z", "startTime": "2026-01-10T12:00:00Z", "generation": 100},
                {"publishTime": "2026-01-09T09:30:00Z", "startTime": "2026-01-10T12:00:00Z", "generation": 200},
                {"publishTime": "2026-01-09T11:30:00Z", "startTime": "2026-01-10T12:00:00Z", "generation": 300},
            ],
        }
    )
    start = ts("2026-01-10T12:00:00")
    assert data.forecast_at(start, ts("2026-01-09T10:00:00"))[1] == 200
    assert data.forecast_at(start, ts("2026-01-09T09:30:00"))[1] == 200  # inclusive
    assert data.forecast_at(start, ts("2026-01-09T07:00:00")) is None


def test_summarize_basic_metrics():
    s = summarize([100, -100, 300], [1000, 1000, 1000])
    assert s["mae"] == pytest.approx(500 / 3)
    assert s["bias"] == pytest.approx(100)
    assert s["nmae_pct"] == pytest.approx(100 * (500 / 3) / 1000)


def test_quantile_interpolates():
    assert quantile([0, 10], 0.5) == 5


client = TestClient(app)


def test_api_day_and_accuracy_on_snapshot():
    r = client.get("/api/day", params={"date": "2026-01-15", "decision_hour": 10})
    assert r.status_code == 200
    body = r.json()
    assert len(body["hourly"]) == 24 and len(body["half_hourly"]) == 48
    assert body["forecast_published"] <= body["decision_cutoff"]

    acc = client.get("/api/accuracy").json()
    assert acc["overall"]["n"] > 600
    assert acc["overall"]["mae"] > 0


def test_api_rejects_out_of_range_date():
    assert client.get("/api/day", params={"date": "2025-12-01"}).status_code == 422
