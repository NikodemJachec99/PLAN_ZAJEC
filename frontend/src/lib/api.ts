import type { Plan, Selection, Status } from "../types";

const API_BASE_URL = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "").replace(/\/$/, "");

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

async function getJson<T>(path: string): Promise<T> {
  // "no-cache" = always revalidate with the server (ETag), never show a stale plan.
  const response = await fetch(apiUrl(path), { cache: "no-cache", headers: { Accept: "application/json" } });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      // keep the status code
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function fetchPlan(): Promise<Plan> {
  return getJson<Plan>("/api/v1/plan");
}

export function fetchStatus(): Promise<Status> {
  return getJson<Status>("/api/v1/status");
}

export async function requestSync(): Promise<boolean> {
  const response = await fetch(apiUrl("/api/v1/sync"), { method: "POST" });
  if (!response.ok) return false;
  const payload = (await response.json()) as { accepted?: boolean };
  return Boolean(payload.accepted);
}

export function calendarUrl(selection: Selection, download: boolean): string {
  const params = new URLSearchParams(selection);
  if (download) params.set("download", "1");
  const path = `/api/v1/calendar.ics?${params.toString()}`;
  if (API_BASE_URL) return apiUrl(path);
  return new URL(path, window.location.origin).toString();
}
