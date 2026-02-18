export type FilterCategory = "subject" | "instructor" | "room" | "group" | "oddzial" | "type";

export interface FilterOptions {
  subject: string[];
  instructor: string[];
  room: string[];
  group: string[];
  oddzial: string[];
  type: string[];
}

export interface MetaResponse {
  timezone: string;
  min_date: string | null;
  max_date: string | null;
  filters: FilterOptions;
}

export interface ScheduleEvent {
  id: string;
  date: string;
  start_time: string;
  end_time: string;
  start_min: number;
  end_min: number;
  subject: string;
  instructor: string;
  room: string;
  group: string;
  oddzial: string;
  type: string;
  source: string;
  layout_col: number;
  layout_cols_total: number;
  color_hsl: string;
}

export interface DaySchedule {
  date: string;
  range_start_min: number;
  range_end_min: number;
  events: ScheduleEvent[];
}

export interface WeekSchedule {
  week_start: string;
  week_end: string;
  days: DaySchedule[];
}

export interface HealthResponse {
  status: string;
  last_reload_at: string | null;
  cache_ttl_seconds: number;
  records: number;
}

export interface ApiError {
  detail: string;
  request_id?: string;
}

export interface ActiveFilters {
  subject: string[];
  instructor: string[];
  room: string[];
  group: string[];
  oddzial: string[];
  type: string[];
  only_magdalenka: boolean;
}

export interface UrlState {
  date: string;
  filters: ActiveFilters;
}
