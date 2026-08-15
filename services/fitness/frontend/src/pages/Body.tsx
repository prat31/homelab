import { useEffect, useState } from "react";
import { getSeries, RangeKey } from "../api";
import { RangePills } from "../components/RangePills";
import { TimeChart } from "../components/TimeChart";

export function BodyPage() {
  const [range, setRange] = useState<RangeKey>("90d");
  const [metric, setMetric] = useState("weight_kg");
  const [points, setPoints] = useState<{ date: string; value: number }[]>([]);

  useEffect(() => {
    getSeries(metric, range).then((payload) => setPoints(payload.points));
  }, [metric, range]);

  return (
    <>
      <div className="row">
        <h2>Body</h2>
        <RangePills value={range} onChange={setRange} />
        <select value={metric} onChange={(event) => setMetric(event.target.value)}>
          <option value="weight_kg">Weight (kg)</option>
          <option value="rhr_bpm">Resting HR</option>
        </select>
      </div>
      <TimeChart points={points} color="#69db7c" />
      <p className="muted">Weight is plotted only on days a measurement exists.</p>
    </>
  );
}
