"""Pure-Python analytics: decision-time forecast selection and forecast error statistics.

Conventions
- All timestamps are timezone-aware UTC internally. January is GMT, so UK local == UTC,
  but conversions go through Europe/London so the logic stays correct across DST.
- error = forecast - actual (positive = forecast over-estimated wind, i.e. you'd under-buy).
- WINDFOR is hourly; it is compared with the actual half-hour that starts at the same time.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
LEAD_BUCKETS = [(0, 6), (6, 12), (12, 18), (18, 24), (24, 30), (30, 36), (36, 42), (42, 48)]


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class WindData:
    actuals: dict[datetime, float]
    # startTime -> sorted list of (publishTime, MW)
    forecasts: dict[datetime, list[tuple[datetime, float]]]
    fetched_at: str

    @classmethod
    def from_payload(cls, payload: dict) -> "WindData":
        actuals = {parse_ts(r["startTime"]): float(r["generation"]) for r in payload["actuals"]}
        fc: dict[datetime, list[tuple[datetime, float]]] = defaultdict(list)
        for r in payload["forecasts"]:
            fc[parse_ts(r["startTime"])].append((parse_ts(r["publishTime"]), float(r["generation"])))
        for v in fc.values():
            v.sort()
        return cls(actuals=actuals, forecasts=dict(fc), fetched_at=payload.get("fetchedAt", ""))

    def forecast_at(self, start: datetime, cutoff: datetime) -> tuple[datetime, float] | None:
        """Latest forecast for `start` published at or before `cutoff`."""
        vintages = self.forecasts.get(start)
        if not vintages:
            return None
        i = bisect.bisect_right(vintages, (cutoff, math.inf))
        return vintages[i - 1] if i else None

    def last_actual_before(self, cutoff: datetime) -> float | None:
        """Most recent half-hour actual that had finished by `cutoff` (used for the persistence baseline)."""
        t = cutoff - timedelta(minutes=30)
        for _ in range(8):
            if t in self.actuals:
                return self.actuals[t]
            t -= timedelta(minutes=30)
        return None


def decision_cutoff(delivery_day: date, decision_hour: int) -> datetime:
    """Day-ahead purchase decision is taken on D-1 at `decision_hour` UK local time."""
    local = datetime.combine(delivery_day - timedelta(days=1), time(decision_hour), tzinfo=UK)
    return local.astimezone(timezone.utc)


def delivery_slots(delivery_day: date, step_minutes: int) -> list[datetime]:
    start = datetime.combine(delivery_day, time(0), tzinfo=UK).astimezone(timezone.utc)
    end = datetime.combine(delivery_day + timedelta(days=1), time(0), tzinfo=UK).astimezone(timezone.utc)
    out, t = [], start
    while t < end:
        out.append(t)
        t += timedelta(minutes=step_minutes)
    return out


def quantile(values: list[float], q: float) -> float:
    s = sorted(values)
    if not s:
        return float("nan")
    pos = (len(s) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def summarize(errors: list[float], actuals: list[float]) -> dict:
    n = len(errors)
    if n == 0:
        return {"n": 0}
    abs_e = [abs(e) for e in errors]
    mean_actual = sum(actuals) / n
    return {
        "n": n,
        "mae": sum(abs_e) / n,
        "rmse": math.sqrt(sum(e * e for e in errors) / n),
        "bias": sum(errors) / n,
        # MAE relative to mean actual: robust where plain MAPE explodes on low-wind hours.
        "nmae_pct": 100 * (sum(abs_e) / n) / mean_actual if mean_actual else None,
        "p10": quantile(errors, 0.10),
        "p50": quantile(errors, 0.50),
        "p90": quantile(errors, 0.90),
        "max_abs": max(abs_e),
    }


def decision_pairs(data: WindData, days: list[date], decision_hour: int) -> list[dict]:
    """One row per hourly delivery slot: the forecast the buyer actually had, and what happened."""
    rows = []
    for d in days:
        cutoff = decision_cutoff(d, decision_hour)
        persistence = data.last_actual_before(cutoff)
        for start in delivery_slots(d, 60):
            fc = data.forecast_at(start, cutoff)
            actual = data.actuals.get(start)
            if fc is None or actual is None:
                continue
            rows.append(
                {
                    "day": d,
                    "start": start,
                    "publish": fc[0],
                    "forecast": fc[1],
                    "actual": actual,
                    "error": fc[1] - actual,
                    "lead_h": (start - fc[0]).total_seconds() / 3600,
                    "persistence": persistence,
                }
            )
    return rows


def accuracy_report(data: WindData, days: list[date], decision_hour: int) -> dict:
    pairs = decision_pairs(data, days, decision_hour)
    errors = [p["error"] for p in pairs]
    acts = [p["actual"] for p in pairs]
    overall = summarize(errors, acts)

    pers = [p for p in pairs if p["persistence"] is not None]
    pers_mae = sum(abs(p["persistence"] - p["actual"]) for p in pers) / len(pers) if pers else None
    fc_mae_same = sum(abs(p["error"]) for p in pers) / len(pers) if pers else None
    # How much of the error is a constant offset? (Removable by a simple bias correction.)
    if errors:
        b = overall["bias"]
        overall["debiased_mae"] = sum(abs(e - b) for e in errors) / len(errors)
    overall["persistence_mae"] = pers_mae
    overall["skill_vs_persistence_pct"] = (
        100 * (1 - fc_mae_same / pers_mae) if pers_mae and fc_mae_same is not None else None
    )

    by_hour: dict[int, list[dict]] = defaultdict(list)
    for p in pairs:
        by_hour[p["start"].astimezone(UK).hour].append(p)
    hour_rows = [
        {"hour": h, **summarize([p["error"] for p in ps], [p["actual"] for p in ps])}
        for h, ps in sorted(by_hour.items())
    ]

    by_day: dict[date, list[dict]] = defaultdict(list)
    for p in pairs:
        by_day[p["day"]].append(p)
    day_rows = [
        {
            "date": d.isoformat(),
            **summarize([p["error"] for p in ps], [p["actual"] for p in ps]),
            "mean_actual": sum(p["actual"] for p in ps) / len(ps),
        }
        for d, ps in sorted(by_day.items())
    ]

    # Lead-time curve uses every forecast vintage (not just decision-time ones) for the same delivery days.
    day_set = set(days)
    lead_err: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for start, vintages in data.forecasts.items():
        if start.astimezone(UK).date() not in day_set or start not in data.actuals:
            continue
        actual = data.actuals[start]
        for publish, mw in vintages:
            lead = (start - publish).total_seconds() / 3600
            for i, (lo, hi) in enumerate(LEAD_BUCKETS):
                if lo <= lead < hi:
                    lead_err[i].append((mw - actual, actual))
                    break
    lead_rows = [
        {
            "bucket": f"{lo}-{hi}h",
            **summarize([e for e, _ in lead_err[i]], [a for _, a in lead_err[i]]),
        }
        for i, (lo, hi) in enumerate(LEAD_BUCKETS)
        if lead_err[i]
    ]

    width = 500
    hist: dict[int, int] = defaultdict(int)
    for e in errors:
        hist[math.floor(e / width) * width] += 1
    hist_rows = [{"bin": b, "label": f"{b:+,}", "count": c} for b, c in sorted(hist.items())]

    return {
        "decision_hour": decision_hour,
        "overall": overall,
        "by_hour": hour_rows,
        "by_day": day_rows,
        "by_lead": lead_rows,
        "histogram": hist_rows,
        "hist_bin_mw": width,
    }


def day_view(data: WindData, day: date, decision_hour: int, band: tuple[float, float]) -> dict:
    """Everything the buyer needs on screen for one delivery day."""
    cutoff = decision_cutoff(day, decision_hour)
    lo_q, hi_q = band
    hourly = []
    for start in delivery_slots(day, 60):
        fc = data.forecast_at(start, cutoff)
        latest = data.forecast_at(start, start)
        actual = data.actuals.get(start)
        value = fc[1] if fc else None
        hourly.append(
            {
                "time": iso(start),
                "label": start.astimezone(UK).strftime("%H:%M"),
                "forecast": value,
                "published": iso(fc[0]) if fc else None,
                # forecast - actual quantiles -> actual is likely in [forecast - p90, forecast - p10]
                "band_low": max(0.0, value - hi_q) if value is not None else None,
                "band_high": value - lo_q if value is not None else None,
                "latest_forecast": latest[1] if latest else None,
                "actual": actual,
            }
        )
    half_hourly = [
        {"time": iso(t), "label": t.astimezone(UK).strftime("%H:%M"), "actual": data.actuals.get(t)}
        for t in delivery_slots(day, 30)
    ]
    fc_vals = [h["forecast"] for h in hourly if h["forecast"] is not None]
    act_vals = [h["actual"] for h in half_hourly if h["actual"] is not None]
    pub = next((h["published"] for h in hourly if h["published"]), None)
    return {
        "date": day.isoformat(),
        "decision_cutoff": iso(cutoff),
        "forecast_published": pub,
        "hourly": hourly,
        "half_hourly": half_hourly,
        "summary": {
            "forecast_energy_mwh": sum(fc_vals) if fc_vals else None,
            "actual_energy_mwh": sum(act_vals) * 0.5 if act_vals else None,
            "forecast_min": min(fc_vals) if fc_vals else None,
            "forecast_max": max(fc_vals) if fc_vals else None,
            "band_mw": [lo_q, hi_q],
        },
    }
