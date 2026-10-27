# Wind Forecast Desk

A pilot web app for a UK utility's **day-ahead power purchasing team**. It shows:

1. **Day-ahead view**: for any delivery day, the wind forecast the buyer could actually see at decision time (D-1, default 10:00 UK, adjustable), a likely range from historical error, and the actual outturn for back-testing.
2. **Forecast accuracy**: how good those forecasts were in January 2026. MAE, RMSE, bias, error as a % of mean actual, P10/P50/P90, skill against a persistence baseline, and breakdowns by lead time, delivery hour and day.

Data: national wind generation from **Elexon BMRS** only:
- Actuals: [`FUELHH`](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream), `fuelType = WIND`, half-hourly.
- Forecasts: [`WINDFOR`](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream), hourly, multiple vintages (`publishTime`) per target `startTime`.

**Live app:** _added after deploy_

## Key findings (January 2026, 10:00 D-1 decision)

| Metric | Value |
|---|---|
| MAE | ~2.0 GW (17.7% of mean actual wind) |
| Bias (forecast − actual) | **+1.7 GW**: the forecast is systematically too high |
| MAE after removing that constant bias | ~1.4 GW |
| Skill vs persistence | ~51% lower error than holding the last actual flat |
| Lead time | MAE rises from ~1.65 GW (0–6h ahead) to ~2.3 GW (42–48h ahead) |

The bias matters most for buyers. Taken at face value, the forecast would lead them to under-buy: renewables arrive below forecast, and the shortfall has to be bought later at intraday or imbalance prices. Part of the gap is likely definitional (FUELHH covers metered transmission-connected wind, and outturn is reduced by curtailment), so a bias correction should be validated with the client before going live.

## Method

- **Scope:** purchase decisions made in January 2026, so delivery days **2 Jan – 1 Feb 2026**.
- **Decision-time forecast:** for each hourly delivery slot, the latest `WINDFOR` vintage with `publishTime <= decision time` on D-1. This matches what was available at the time, with no look-ahead. Decision time is a parameter (`decision_hour`), with timezones handled via `Europe/London`.
- **Error:** `forecast − actual`, comparing each hourly forecast with the FUELHH half-hour that starts at the same time.
- **Metrics:** MAE, RMSE, bias, nMAE (MAE ÷ mean actual; plain MAPE breaks down at low wind), error quantiles, and a persistence baseline (last finished actual at decision time).
- **Lead-time curve:** uses *all* forecast vintages for the same delivery days, bucketed by `startTime − publishTime`.
- **Likely range:** decision forecast shifted by the P10–P90 of January's decision-time errors.

## Repository layout

```
backend/
  app/
    elexon.py        # Elexon BMRS client (FUELHH, WINDFOR stream endpoints)
    analytics.py     # decision-time forecast selection + error statistics (pure Python)
    main.py          # FastAPI app: /api/meta, /api/day, /api/accuracy (+ serves built UI in Docker)
  scripts/fetch_data.py   # refreshes the January 2026 snapshot from Elexon
  data/wind_jan2026.json.gz  # cached snapshot (actuals + forecasts ≤48h ahead)
  tests/test_analytics.py    # unit + API tests
  requirements.txt
frontend/            # React + TypeScript + Vite + Recharts
  src/App.tsx, src/api.ts, src/components/{DayAhead,Accuracy,ui}.tsx, src/styles.css
api/index.py         # Vercel serverless entry (re-exports the FastAPI app)
vercel.json          # Vercel build + routing (static UI + Python API)
Dockerfile, docker-compose.yml  # single container: builds UI, serves UI + API on :8000
```

### Why a snapshot?
The scope is a fixed historical month. Caching it (~80 KB gzipped) keeps the app fast and deterministic, and independent of Elexon's uptime during a demo. `python -m scripts.fetch_data` regenerates it from the live API.

## Running it

**Docker (recommended)**
```bash
docker compose up --build
# open http://localhost:8000
```

**Local development**
```bash
# API
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
uvicorn app.main:app --reload --port 8000

# UI (new terminal), proxies /api to :8000
cd frontend
npm install
npm run dev   # http://localhost:5173
```

**Tests and data refresh**
```bash
cd backend && pytest -q
cd backend && python -m scripts.fetch_data
```

## API

| Endpoint | Description |
|---|---|
| `GET /api/meta` | date range, data provenance |
| `GET /api/day?date=2026-01-15&decision_hour=10` | decision-time forecast, likely range, latest forecast, actuals for one delivery day |
| `GET /api/accuracy?decision_hour=10` | overall metrics + breakdowns by lead time, hour, day, error histogram |

## Use of AI tools

AI coding assistants (Claude via OpenCode) were used to help scaffold and write parts of the code and documentation. The domain framing, metric choices and analysis were reviewed by me.
