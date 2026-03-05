import type {
  ActiveFilters,
  ApiError,
  DaySchedule,
  HealthResponse,
  MetaResponse,
  RuntimeSettings,
  RuntimeSettingsUpdatePayload,
  WeekSchedule,
} from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

function withBase(path: string): string {
  return `${API_BASE_URL.replace(/\/$/, "")}${path}`;
}

interface RequestOptions {
  method?: string;
  headers?: Record<string, string>;
  body?: BodyInit | null;
}

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(withBase(path), {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(options.headers ?? {}),
    },
    body: options.body,
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

function passwordHeaders(password: string): Record<string, string> {
  return { "x-settings-password": password };
}

export function fetchMeta(): Promise<MetaResponse> {
  return requestJson<MetaResponse>("/api/v1/meta");
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/v1/health");
}

export function fetchDaySchedule(date: string, filters: ActiveFilters): Promise<DaySchedule> {
  return requestJson<DaySchedule>(`/api/v1/schedule/day?date=${encodeURIComponent(date)}${buildFilterQuery(filters)}`);
}

export function fetchWeekSchedule(anchorDate: string, filters: ActiveFilters): Promise<WeekSchedule> {
  return requestJson<WeekSchedule>(
    `/api/v1/schedule/week?anchor_date=${encodeURIComponent(anchorDate)}${buildFilterQuery(filters)}`,
  );
}

export function fetchRuntimeSettings(): Promise<RuntimeSettings> {
  return requestJson<RuntimeSettings>("/api/v1/settings");
}

export function updateRuntimeSettings(
  payload: RuntimeSettingsUpdatePayload,
  password: string,
): Promise<RuntimeSettings> {
  return requestJson<RuntimeSettings>("/api/v1/settings", {
    method: "PUT",
    headers: {
      ...passwordHeaders(password),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function uploadMainScheduleFile(file: File, password: string): Promise<RuntimeSettings> {
  const formData = new FormData();
  formData.append("file", file);
  return requestJson<RuntimeSettings>("/api/v1/settings/files/main", {
    method: "POST",
    headers: passwordHeaders(password),
    body: formData,
  });
}

export function uploadPracticalScheduleFile(file: File, password: string): Promise<RuntimeSettings> {
  const formData = new FormData();
  formData.append("file", file);
  return requestJson<RuntimeSettings>("/api/v1/settings/files/practical", {
    method: "POST",
    headers: passwordHeaders(password),
    body: formData,
  });
}
