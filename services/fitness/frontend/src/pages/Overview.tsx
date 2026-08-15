import { useEffect, useState } from "react";
import { getSummary, MetricPair, RangeKey } from "../api";
import { RangePills } from "../components/RangePills";

function format(value: number, digits = 0) {
  return value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function Card({ label, metric, digits = 0 }: { label: string; metric: MetricPair; digits?: number }) {
  const delta = metric.wow_pct;
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className="value">{format(metric.current, digits)}</div>
      <div className={`delta ${delta != null && delta >= 0 ? "up" : "down"}`}>
        {delta == null ? "vs prior period n/a" : `${delta >= 0 ? "+" : ""}${delta.toFixed(0)}% vs prior`}
      </div>
    </div>
  );
}

export function OverviewPage() {
  const [range, setRange] = useState<RangeKey>("7d");
  const [data, setData] = useState<Record<string, MetricPair> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSummary(range)
      .then((payload) => {
        const metrics = Object.fromEntries(
          Object.entries(payload).filter(([, value]) => typeof value === "object"),
        ) as Record<string, MetricPair>;
        setData(metrics);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [range]);

  return (
    <>
      <div className="row">
        <h2>Overview</h2>
        <RangePills value={range} onChange={setRange} />
      </div>
      {error ? <p className="muted">{error}</p> : null}
      {data ? (
        <div className="grid">
          <Card label="Steps" metric={data.steps} />
          <Card label="Distance km" metric={data.distance_km} digits={1} />
          <Card label="Calories kcal" metric={data.calories_kcal} />
          <Card label="Elevation m" metric={data.elevation_m} />
          <Card label="Sleep hours" metric={data.sleep_hours} digits={1} />
          <Card label="Workout min" metric={data.workout_minutes} />
          <Card label="Resting HR" metric={data.rhr_bpm} />
        </div>
      ) : (
        <p className="muted">Loading…</p>
      )}
    </>
  );
}
