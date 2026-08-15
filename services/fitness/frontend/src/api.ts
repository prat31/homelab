declare global {
  interface Window {
    FITNESS_API_KEY?: string;
  }
}

export type RangeKey = "7d" | "30d" | "90d" | "all";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const apiKey = window.FITNESS_API_KEY;
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export type MetricPair = { current: number; previous: number; wow_pct: number | null };

export function getSummary(range: RangeKey) {
  return request<Record<string, MetricPair | string>>(`/api/summary?range=${range}`);
}

export function getSeries(metric: string, range: RangeKey) {
  return request<{ points: { date: string; value: number }[] }>(`/api/series/${metric}?range=${range}`);
}

export function getWorkouts(range: RangeKey) {
  return request<{ workouts: Record<string, string | number | null>[] }>(`/api/workouts?range=${range}`);
}

export function getSleep(range: RangeKey) {
  return request<{ nights: Record<string, string | number | null>[] }>(`/api/sleep?range=${range}`);
}

export function getBody(range: RangeKey) {
  return request<{ points: Record<string, string | number | null>[] }>(`/api/body?range=${range}`);
}

export function getStatus() {
  return request<Record<string, unknown>>("/api/ingest/status");
}

export function getSources() {
  return request<{ sources: { metric: string; source_package: string; days: number }[] }>("/api/sources");
}

export function pollDrive() {
  return request<Record<string, unknown>>("/api/ingest/drive", { method: "POST" });
}

export function uploadExport(file: File) {
  const body = new FormData();
  body.append("file", file);
  return request<Record<string, unknown>>("/api/ingest", { method: "POST", body });
}
