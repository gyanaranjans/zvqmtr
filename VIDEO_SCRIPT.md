# Video script (max 10 min, unlisted YouTube)

## Part 1: Client pitch (about 4.5 min). Screen: https://zvqmtr.vercel.app

**0:00 Hook (30s)**
"Every morning your team decides how much power to buy for tomorrow. Wind is the biggest unknown in that decision. You want to know two things: what wind is expected tomorrow, and how far you can trust that number. We built Wind Forecast Desk to answer both, using January 2026 as a pilot."

**0:30 Day-ahead view (1.5 min)**
- Point to the decision-time selector: "Your bids are prepared the morning before, so by default we show the forecast as it stood at 10:00 the day before. Change this to match your desk's cut-off, and everything recalculates."
- Pick 15 Jan. "This green line is exactly what you could have seen at decision time, published 09:30. There's no hindsight in it."
- Point to the shaded band: "This is the likely range, based on how wrong the forecast actually was in January. If you're sizing a hedge, this is your 80% range."
- KPI cards: "Expected wind energy 280 GWh, range 9 to 16 GW. The actual came in at 254 GWh, inside the band but below the line."
- Step through a few days with ‹ ›. Show a day where it went well and one where it went badly.

**2:00 Accuracy view (1.5 min)**
- "Over January, the decision-time forecast was off by about 2 GW on average, 18% of mean wind output."
- **Key insight (bias card, highlighted):** "The forecast isn't just noisy, it's consistently too high, by about 1.7 GW. Relying on it at face value means under-buying, and covering that gap later at intraday or imbalance prices."
- "Remove that constant offset and the error drops from 2.0 to 1.4 GW. That's a cheap, immediate win, which we'd validate with you."
- Lead-time chart: "Fresher forecasts are better: 1.65 GW error at 0–6h ahead, 2.3 GW at 42–48h. That's the cost of deciding a day early."
- Skill vs persistence: "It is still far better than naive approaches, with half the error of assuming tomorrow looks like now."
- Daily chart: "These two days in early January were the outliers. Those are the days that drive imbalance costs."

**3:30 Close (45s)**
"Next steps: connect live Elexon feeds so this updates every morning, add solar and demand, and turn the bias finding into a corrected forecast and a recommended buy volume. Happy to run this with your traders for a month."

## Part 2: Tech lead review (about 5 min). Screen: GitHub repo + editor

**0:00 Architecture (1 min)**
- React + TypeScript + Vite + Recharts frontend; Python FastAPI backend.
- Data: two Elexon BMRS stream endpoints, FUELHH (wind, half-hourly actuals) and WINDFOR (hourly, many vintages per target).
- The January snapshot is cached in `backend/data/` (80 KB gz). It's deterministic, fast, and doesn't depend on Elexon being up during a demo. `scripts/fetch_data.py` regenerates it.
- Deploy: Vercel services, with FastAPI on `/api` and Vite for the UI. Docker is a single container that builds the UI and serves UI + API on :8000.

**1:00 Core logic: `backend/app/analytics.py` (2 min)**
- `WindData`: actuals keyed by start time; forecasts grouped by start time, sorted by publish time.
- `forecast_at(start, cutoff)`: bisect for the latest vintage with publishTime ≤ cutoff. This is what prevents look-ahead bias, and it's the most important line in the project.
- `decision_cutoff`: D-1 at a configurable hour, in Europe/London time (DST-safe).
- `accuracy_report`: decision pairs → MAE, RMSE, bias, nMAE (why not MAPE: low-wind hours make it explode), quantiles, persistence baseline, de-biased MAE. The lead-time curve uses all vintages.
- `day_view`: decision forecast + P10–P90 band + latest forecast + actuals.

**3:00 API and frontend (1 min)**
- `main.py`: three endpoints, `lru_cache` on data and reports, input validation (422 on bad dates/hours).
- `api.ts`: typed client. `DayAhead.tsx` merges the hourly forecast onto the half-hourly actual grid. `Accuracy.tsx` holds the charts.

**4:00 Practices and next steps (1 min)**
- Tests: `pytest` covers the cutoff logic, vintage selection (inclusive boundary), metrics and API contract.
- Typed frontend, a small dependency footprint, pure-Python analytics (fast serverless cold starts).
- AI-assisted coding, disclosed in the README.
- Next: scheduled ingestion to a DB, probabilistic/quantile forecasts, bias-correction model with backtest, CI pipeline.
