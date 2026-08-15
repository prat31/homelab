import { useEffect, useState } from "react";
import { getWorkouts, RangeKey } from "../api";
import { RangePills } from "../components/RangePills";

export function WorkoutsPage() {
  const [range, setRange] = useState<RangeKey>("30d");
  const [rows, setRows] = useState<Record<string, string | number | null>[]>([]);

  useEffect(() => {
    getWorkouts(range).then((payload) => setRows(payload.workouts));
  }, [range]);

  return (
    <>
      <div className="row">
        <h2>Workouts</h2>
        <RangePills value={range} onChange={setRange} />
      </div>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Type</th>
              <th>Minutes</th>
              <th>Avg HR</th>
              <th>Max HR</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={String(row.uuid)}>
                <td>{String(row.local_date)}</td>
                <td>{String(row.exercise_name)}</td>
                <td>{Math.round(Number(row.duration_sec) / 60)}</td>
                <td>{row.avg_hr ? Math.round(Number(row.avg_hr)) : "—"}</td>
                <td>{row.max_hr ? Math.round(Number(row.max_hr)) : "—"}</td>
                <td className="muted">{String(row.source_package ?? "")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
