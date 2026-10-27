import { useEffect, useState } from "react";
import { api, Meta, ukTime } from "./api";
import { Accuracy } from "./components/Accuracy";
import { DayAhead } from "./components/DayAhead";
import { Card } from "./components/ui";

type Tab = "day" | "accuracy" | "method";

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [tab, setTab] = useState<Tab>("day");
  const [hour, setHour] = useState(10);

  useEffect(() => {
    api.meta().then(setMeta);
  }, []);

  return (
    <div className="app">
      <header>
        <div>
          <h1>Wind Forecast Desk</h1>
          <p className="muted">UK national wind generation for day-ahead power purchasing · January 2026</p>
        </div>
        <label className="hour">
          <span className="eyebrow">Decision time (D-1, UK)</span>
          <select value={hour} onChange={(e) => setHour(Number(e.target.value))}>
            {Array.from({ length: 24 }, (_, h) => (
              <option key={h} value={h}>{`${String(h).padStart(2, "0")}:00`}</option>
            ))}
          </select>
        </label>
      </header>

      <nav className="tabs">
        {(
          [
            ["day", "Day-ahead view"],
            ["accuracy", "Forecast accuracy"],
            ["method", "Data & method"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </nav>

      {!meta ? (
        <Card><div className="skeleton" /></Card>
      ) : tab === "day" ? (
        <DayAhead meta={meta} hour={hour} />
      ) : tab === "accuracy" ? (
        <Accuracy hour={hour} />
      ) : (
        <Card title="Data & method">
          <ul className="method">
            <li><b>Source:</b> {meta.source}. Snapshot fetched {ukTime(meta.fetched_at)}: {meta.n_actuals.toLocaleString()} half-hourly actuals, {meta.n_forecast_points.toLocaleString()} forecast points.</li>
            <li><b>Scope:</b> purchase decisions made in January 2026, i.e. delivery days {meta.first_day} to {meta.last_day}.</li>
            <li><b>Decision-time forecast:</b> for each delivery hour, the latest WINDFOR forecast published at or before the decision time on the previous day (default 10:00 UK, adjustable above). This is what the buyer could actually see, with no look-ahead.</li>
            <li><b>Error:</b> forecast minus actual (FUELHH, fuelType WIND) at the same start time. Positive means the forecast expected more wind than arrived, so more power would have been needed from the market.</li>
            <li><b>Metrics:</b> MAE, RMSE, bias, MAE as a % of mean actual (MAPE is unstable at low wind), P10/P50/P90 of error, and skill against a persistence baseline (the last known actual at decision time, held flat).</li>
            <li><b>Likely range:</b> the forecast adjusted by January's P10–P90 decision-time error, to size hedging or reserve purchases.</li>
          </ul>
        </Card>
      )}
      <footer className="muted small">Data: Elexon BMRS (Insights Solution). Built as a pilot for the day-ahead trading desk.</footer>
    </div>
  );
}
