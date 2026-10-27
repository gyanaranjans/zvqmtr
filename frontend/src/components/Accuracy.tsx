import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Accuracy as AccuracyT, api, mw } from "../api";
import { Card, Kpi } from "./ui";

const gw = (v: number) => `${(v / 1000).toFixed(1)} GW`;

export function Accuracy({ hour }: { hour: number }) {
  const [data, setData] = useState<AccuracyT | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    api.accuracy(hour).then(setData).catch((e) => setError(String(e.message ?? e)));
  }, [hour]);

  if (error) return <Card><div className="error">{error}</div></Card>;
  if (!data) return <Card><div className="skeleton" /></Card>;
  const o = data.overall;

  return (
    <div className="stack">
      <div className="kpis">
        <Kpi label="Mean absolute error" value={mw(o.mae)} hint={`${o.nmae_pct?.toFixed(1)}% of mean actual · ${o.n} hours`} />
        <Kpi label="RMSE" value={mw(o.rmse)} hint="Penalises large misses" />
        <Kpi
          label="Bias (forecast − actual)"
          value={mw(o.bias)}
          hint={o.bias > 0 ? "Forecast systematically too high → risk of under-buying" : "Forecast systematically too low"}
          tone={Math.abs(o.bias) > o.mae * 0.5 ? "warn" : undefined}
        />
        <Kpi label="MAE after bias correction" value={mw(o.debiased_mae)} hint="Error left once the constant offset is removed" />
        <Kpi
          label="Skill vs persistence"
          value={o.skill_vs_persistence_pct == null ? "–" : `${o.skill_vs_persistence_pct.toFixed(0)}%`}
          hint={`Persistence MAE ${mw(o.persistence_mae)} (last actual held flat)`}
        />
      </div>

      <div className="grid2">
        <Card title="Error grows with forecast lead time">
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={data.by_lead}>
              <CartesianGrid stroke="#e7ebf0" vertical={false} />
              <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={gw} tick={{ fontSize: 12 }} width={56} />
              <Tooltip formatter={(v: number) => mw(v)} />
              <Legend />
              <Bar dataKey="mae" name="MAE" fill="#0f766e" radius={[4, 4, 0, 0]} />
              <Line dataKey="bias" name="Bias" stroke="#b45309" strokeWidth={2} />
            </ComposedChart>
          </ResponsiveContainer>
          <p className="muted small">All forecast vintages for the same delivery days, grouped by hours between publish and delivery.</p>
        </Card>

        <Card title="Distribution of decision-time errors">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.histogram}>
              <CartesianGrid stroke="#e7ebf0" vertical={false} />
              <XAxis dataKey="bin" tickFormatter={gw} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} width={40} />
              <Tooltip
                labelFormatter={(b: number) => `${gw(b)} to ${gw(b + data.hist_bin_mw)}`}
                formatter={(v: number) => [`${v} hours`, "Count"]}
              />
              <ReferenceLine x={0} stroke="#1e293b" />
              <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                {data.histogram.map((h) => (
                  <Cell key={h.bin} fill={h.bin >= 0 ? "#b45309" : "#2563eb"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="muted small">
            Orange = forecast above actual. P10 {mw(o.p10)}, median {mw(o.p50)}, P90 {mw(o.p90)}.
          </p>
        </Card>
      </div>

      <Card title="Daily error across January (decision-time forecast)">
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={data.by_day}>
            <CartesianGrid stroke="#e7ebf0" vertical={false} />
            <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(8)} tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={gw} tick={{ fontSize: 12 }} width={56} />
            <Tooltip formatter={(v: number) => mw(v)} />
            <Legend />
            <Bar dataKey="mae" name="Daily MAE" fill="#0f766e" radius={[3, 3, 0, 0]} />
            <Line dataKey="bias" name="Daily bias" stroke="#b45309" strokeWidth={2} dot={false} />
            <Line dataKey="mean_actual" name="Mean actual wind" stroke="#94a3b8" strokeDasharray="5 4" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Error by hour of delivery (UK time)">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={data.by_hour}>
            <CartesianGrid stroke="#e7ebf0" vertical={false} />
            <XAxis dataKey="hour" tickFormatter={(h: number) => `${String(h).padStart(2, "0")}:00`} tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={gw} tick={{ fontSize: 12 }} width={56} />
            <Tooltip formatter={(v: number) => mw(v)} />
            <Bar dataKey="mae" name="MAE" fill="#0f766e" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}
