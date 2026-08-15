import { useEffect, useState } from "react";
import { getSeries, getSleep, RangeKey } from "../api";
import { RangePills } from "../components/RangePills";
import { TimeChart } from "../components/TimeChart";

export function SleepPage() {
  const [range, setRange] = useState<RangeKey>("30d");
  const [points, setPoints] = useState<{ date: string; value: number }[]>([]);
  const [nights, setNights] = useState<Record<string, string | number | null>[]>([]);

  useEffect(() => {
    getSeries("sleep_hours", range).then((payload) => setPoints(payload.points));
    getSleep(range).then((payload) => setNights(payload.nights));
  }, [range]);

  return (
    <>
      <div className="row">
        <h2>Sleep</h2>
        <RangePills value={range} onChange={setRange} />
      </div>
      <TimeChart points={points} color="#74c0fc" />
      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Hours</th>
              <th>Light</th>
              <th>Deep</th>
              <th>REM</th>
              <th>Awake</th>
            </tr>
          </thead>
          <tbody>
            {nights.map((night) => (
              <tr key={String(night.uuid)}>
                <td>{String(night.local_date)}</td>
                <td>{(Number(night.duration_sec) / 3600).toFixed(1)}</td>
                <td>{(Number(night.light_sec) / 3600).toFixed(1)}</td>
                <td>{(Number(night.deep_sec) / 3600).toFixed(1)}</td>
                <td>{(Number(night.rem_sec) / 3600).toFixed(1)}</td>
                <td>{(Number(night.awake_sec) / 3600).toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
