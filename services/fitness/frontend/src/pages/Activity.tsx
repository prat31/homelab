import { useEffect, useState } from "react";
import { getSeries, RangeKey } from "../api";
import { RangePills } from "../components/RangePills";
import { TimeChart } from "../components/TimeChart";

const metrics = [
  ["steps", "Steps"],
  ["distance_km", "Distance (km)"],
  ["calories_kcal", "Calories (kcal)"],
  ["elevation_m", "Elevation (m)"],
];

export function ActivityPage() {
  const [range, setRange] = useState<RangeKey>("30d");
  const [metric, setMetric] = useState("steps");
  const [points, setPoints] = useState<{ date: string; value: number }[]>([]);

  useEffect(() => {
    getSeries(metric, range).then((payload) => setPoints(payload.points));
  }, [metric, range]);

  return (
    <>
      <div className="row">
        <h2>Activity</h2>
        <RangePills value={range} onChange={setRange} />
        <select value={metric} onChange={(event) => setMetric(event.target.value)}>
          {metrics.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <TimeChart points={points} />
    </>
  );
}
