export type Stats = {
  n: number;
  mae: number;
  rmse: number;
  bias: number;
  nmae_pct: number | null;
  p10: number;
  p50: number;
  p90: number;
  max_abs: number;
};

export type Meta = {
  first_day: string;
  last_day: string;
  default_decision_hour: number;
  fetched_at: string;
  n_actuals: number;
  n_forecast_points: number;
  source: string;
};

export type HourRow = {
  time: string;
  label: string;
  forecast: number | null;
  published: string | null;
  band_low: number | null;
  band_high: number | null;
  latest_forecast: number | null;
  actual: number | null;
};

export type DayView = {
  date: string;
  decision_cutoff: string;
  forecast_published: string | null;
  hourly: HourRow[];
  half_hourly: { time: string; label: string; actual: number | null }[];
  summary: {
    forecast_energy_mwh: number | null;
    actual_energy_mwh: number | null;
    forecast_min: number | null;
    forecast_max: number | null;
    band_mw: [number, number];
  };
};

export type Accuracy = {
  decision_hour: number;
  overall: Stats & {
    debiased_mae: number;
    persistence_mae: number | null;
    skill_vs_persistence_pct: number | null;
  };
  by_hour: (Stats & { hour: number })[];
  by_day: (Stats & { date: string; mean_actual: number })[];
  by_lead: (Stats & { bucket: string })[];
  histogram: { bin: number; label: string; count: number }[];
  hist_bin_mw: number;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
  return res.json();
}

export const api = {
  meta: () => get<Meta>("/api/meta"),
  day: (date: string, hour: number) => get<DayView>(`/api/day?date=${date}&decision_hour=${hour}`),
  accuracy: (hour: number) => get<Accuracy>(`/api/accuracy?decision_hour=${hour}`),
};

export const mw = (v: number | null | undefined, digits = 0) =>
  v == null ? "–" : `${v.toLocaleString("en-GB", { maximumFractionDigits: digits })} MW`;

export const gwh = (mwh: number | null | undefined) =>
  mwh == null ? "–" : `${(mwh / 1000).toLocaleString("en-GB", { maximumFractionDigits: 1 })} GWh`;

export const ukTime = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString("en-GB", {
        timeZone: "Europe/London",
        weekday: "short",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "–";
