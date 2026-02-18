import type { ActiveFilters, ApiError, DaySchedule, HealthResponse, MetaResponse, WeekSchedule } from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

function withBase(path: string): string {
  return `${API_BASE_URL.replace(/\/$/, "")}${path}`;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(withBase(path), {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let payload: ApiError | null = null;
    try {
      payload = (await response.json()) as ApiError;
    } catch {
      payload = null;
    }

    throw new Error(payload?.detail ?? `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

function buildFilterQuery(filters: ActiveFilters): string {
  const params = new URLSearchParams();

  filters.subject.forEach((value) => params.append("subject", value));
  filters.instructor.forEach((value) => params.append("instructor", value));
  filters.room.forEach((value) => params.append("room", value));
  filters.group.forEach((value) => params.append("group", value));
  filters.oddzial.forEach((value) => params.append("oddzial", value));
  filters.type.forEach((value) => params.append("type", value));

  if (filters.only_magdalenka) {
    params.set("only_magdalenka", "true");
  }

  const query = params.toString();
  return query ? `&${query}` : "";
}

export function fetchMeta(): Promise<MetaResponse> {
  return fetchJson<MetaResponse>("/api/v1/meta");
}

export function fetchHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/api/v1/health");
}

export function fetchDaySchedule(date: string, filters: ActiveFilters): Promise<DaySchedule> {
  return fetchJson<DaySchedule>(`/api/v1/schedule/day?date=${encodeURIComponent(date)}${buildFilterQuery(filters)}`);
}

export function fetchWeekSchedule(anchorDate: string, filters: ActiveFilters): Promise<WeekSchedule> {
  return fetchJson<WeekSchedule>(
    `/api/v1/schedule/week?anchor_date=${encodeURIComponent(anchorDate)}${buildFilterQuery(filters)}`,
  );
}
