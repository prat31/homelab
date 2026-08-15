import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function TimeChart({ points, color = "#fa5252" }: { points: { date: string; value: number }[]; color?: string }) {
  return (
    <div className="card chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points}>
          <CartesianGrid stroke="#2a3140" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fill: "#8b95a7", fontSize: 12 }} minTickGap={24} />
          <YAxis tick={{ fill: "#8b95a7", fontSize: 12 }} width={48} />
          <Tooltip contentStyle={{ background: "#171b22", border: "1px solid #2a3140" }} />
          <Line type="monotone" dataKey="value" stroke={color} dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
