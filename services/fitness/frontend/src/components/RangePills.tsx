import { RangeKey } from "../api";

export function RangePills({ value, onChange }: { value: RangeKey; onChange: (value: RangeKey) => void }) {
  return (
    <div className="row range">
      {(["7d", "30d", "90d", "all"] as RangeKey[]).map((item) => (
        <button key={item} className={item === value ? "active" : ""} onClick={() => onChange(item)}>
          {item}
        </button>
      ))}
    </div>
  );
}
