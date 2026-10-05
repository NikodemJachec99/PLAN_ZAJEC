export type Mode = "onsite" | "remote" | "unassigned";

export interface PlanEvent {
  id: string;
  date: string;
  start: string;
  end: string;
  parts: [string, string][];
  subject: string;
  subject_key: string;
  kind: "class" | "practical";
  type: string;
  type_label: string;
  type_short: string;
  instructor: string;
  room: string;
  code: string;
  dept: string;
  where: string;
  where_short: string;
  place: string;
  mode: Mode;
  group: string;
  groups: string[];
  note: string;
  cancelled: boolean;
  time_uncertain: boolean;
  csm: boolean;
  source: string;
}

export interface Subject {
  key: string;
  name: string;
  short: string;
  hue: number | null;
}

export interface Dimension {
  id: string;
  label: string;
  options: string[];
}

export interface SourceInfo {
  id: string;
  kind: "main" | "practical";
  label: string;
  name: string;
  url: string;
  origin: "site" | "seed" | "manual";
  sha256: string;
  as_of: string | null;
  fetched_at: string | null;
  last_modified: string | null;
  events: number;
  stale: boolean;
  warnings: string[];
}

export interface PlanMeta {
  year: string;
  level: string;
  academic_year: string;
  semester: string;
  notes: string[];
}

export interface Plan {
  version: string;
  generated_at: string;
  meta: PlanMeta;
  sources: SourceInfo[];
  subjects: Subject[];
  dimensions: Dimension[];
  events: PlanEvent[];
}

export interface SyncInfo {
  page_url: string;
  interval_seconds: number;
  last_checked_at: string | null;
  last_success_at: string | null;
  last_changed_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
  consecutive_failures: number;
  links_found: number;
  running: boolean;
  healthy: boolean;
}

export interface Status {
  version: string | null;
  now: string;
  sync: SyncInfo;
  sources: SourceInfo[];
}

export type Selection = Record<string, string>;

export type View = "dzień" | "tydzień" | "kalendarz" | "lista";
