import { useEffect, useState } from "react";
import { getSources, getStatus, pollDrive, uploadExport } from "../api";

export function DataPage() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [sources, setSources] = useState<{ metric: string; source_package: string; days: number }[]>([]);
  const [message, setMessage] = useState<string>("");

  const refresh = () => {
    getStatus().then(setStatus);
    getSources().then((payload) => setSources(payload.sources));
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <>
      <div className="row">
        <h2>Data</h2>
        <button
          className="primary"
          onClick={() => {
            setMessage("Polling Drive…");
            pollDrive()
              .then((result) => {
                setMessage(JSON.stringify(result));
                refresh();
              })
              .catch((err: Error) => setMessage(err.message));
          }}
        >
          Poll Google Drive
        </button>
        <input
          type="file"
          accept=".db,.sqlite,.sqlite3"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            setMessage("Uploading…");
            uploadExport(file)
              .then((result) => {
                setMessage(JSON.stringify(result));
                refresh();
              })
              .catch((err: Error) => setMessage(err.message));
          }}
        />
      </div>
      <p className="muted">{message}</p>
      <div className="card">
        <pre>{JSON.stringify(status, null, 2)}</pre>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Source</th>
              <th>Days</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((row) => (
              <tr key={`${row.metric}-${row.source_package}`}>
                <td>{row.metric}</td>
                <td>{row.source_package}</td>
                <td>{row.days}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
