import { useEffect, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, DayView, gwh, Meta, mw, ukTime } from "../api";
import { Card, Kpi } from "./ui";

type Props = { meta: Meta; hour: number };

export function DayAhead({ meta, hour }: Props) {
  const [date, setDate] = useState("2026-01-15");
  const [view, setView] = useState<DayView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    api.day(date, hour).then(setView).catch((e) => setError(String(e.message ?? e)));
  }, [date, hour]);

  // Merge hourly forecast rows onto the half-hourly actual grid so both draw on one axis.
  const series = useMemo(() => {
    if (!view) return [];
    const byTime = new Map(view.hourly.map((h) => [h.time, h]));
    return view.half_hourly.map((p) => {
      const h = byTime.get(p.time);
      return {
        label: p.label,
        actual: p.actual,
        forecast: h?.forecast ?? null,
        latest: h?.latest_forecast ?? null,
        band: h && h.band_low != null && h.band_high != null ? [h.band_low, h.band_high] : null,
      };
    });
  }, [view]);

  const shift = (days: number) => {
    const d = new Date(date + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + days);
    const next = d.toISOString().slice(0, 10);
    if (next >= meta.first_day && next <= meta.last_day) setDate(next);
  };

  const s = view?.summary;
  return (
    <div className="stack">
      <Card>
        <div className="toolbar">
          <div>
            <div className="eyebrow">Delivery day</div>
            <div className="row">
              <button className="ghost" onClick={() => shift(-1)} aria-label="Previous day">‹</button>
              <input
                type="date"
                value={date}
                min={meta.first_day}
                max={meta.last_day}
                onChange={(e) => e.target.value && setDate(e.target.value)}
              />
              <button className="ghost" onClick={() => shift(1)} aria-label="Next day">›</button>
            </div>
          </div>
          <div className="muted small">
            Decision taken <b>{view ? ukTime(view.decision_cutoff) : "–"}</b> (D-1, UK time)
            <br />
            Using forecast published <b>{view ? ukTime(view.forecast_published) : "–"}</b>
          </div>
        </div>
      </Card>

      {error && <Card><div className="error">{error}</div></Card>}

      <div className="kpis">
        <Kpi label="Forecast wind energy" value={gwh(s?.forecast_energy_mwh)} hint="Sum of hourly forecast at decision time" />
        <Kpi label="Forecast range" value={s ? `${mw(s.forecast_min)} – ${mw(s.forecast_max)}` : "–"} hint="Min / max hourly forecast" />
        <Kpi
          label="Likely error (P10–P90)"
          value={s ? `${mw(-s.band_mw[1])} to ${mw(-s.band_mw[0])}` : "–"}
          hint="Actual vs forecast, from January history"
        />
        <Kpi label="Actual wind energy" value={gwh(s?.actual_energy_mwh)} hint="Outturn (FUELHH), for back-testing" />
      </div>

      <Card title="Wind generation: forecast at decision time vs actual">
        <div className="chart">
          <ResponsiveContainer width="100%" height={380}>
            <ComposedChart data={series} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
              <CartesianGrid stroke="#e7ebf0" vertical={false} />
              <XAxis dataKey="label" interval={5} tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)} GW`} tick={{ fontSize: 12 }} width={56} />
              <Tooltip
                formatter={(v: number | number[], name: string) =>
                  Array.isArray(v) ? [`${mw(v[0])} – ${mw(v[1])}`, name] : [mw(v), name]
                }
              />
              <Legend />
              <Area dataKey="band" name="Likely range (P10–P90)" stroke="none" fill="#0f766e" fillOpacity={0.12} connectNulls />
              <Line dataKey="forecast" name="Forecast at decision" stroke="#0f766e" strokeWidth={2.5} dot={false} connectNulls />
              <Line dataKey="latest" name="Latest forecast before delivery" stroke="#94a3b8" strokeDasharray="5 4" dot={false} connectNulls />
              <Line dataKey="actual" name="Actual" stroke="#1e293b" strokeWidth={1.5} dot={false} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="muted small">
          The shaded band is the forecast shifted by the 10th–90th percentile of January's decision-time errors.
          WINDFOR is hourly and the actuals are half-hourly; both are in MW.
        </p>
      </Card>
    </div>
  );
}
