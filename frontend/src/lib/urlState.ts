import type { ActiveFilters, FilterCategory, UrlState } from "../types";

export const FILTER_CATEGORIES: FilterCategory[] = ["subject", "instructor", "room", "group", "oddzial", "type"];

export function createDefaultFilters(): ActiveFilters {
  return {
    subject: [],
    instructor: [],
    room: [],
    group: [],
    oddzial: [],
    type: [],
    only_magdalenka: false,
  };
}

export function readUrlState(defaultDate: string): UrlState {
  if (typeof window === "undefined") {
    return { date: defaultDate, filters: createDefaultFilters() };
  }

  const params = new URLSearchParams(window.location.search);
  const date = params.get("date") ?? defaultDate;
  const filters = createDefaultFilters();

  FILTER_CATEGORIES.forEach((category) => {
    filters[category] = params.getAll(category).filter(Boolean);
  });

  filters.only_magdalenka = params.get("only_magdalenka") === "1";

  return { date, filters };
}

export function writeUrlState(state: UrlState): void {
  if (typeof window === "undefined") {
    return;
  }

  const params = new URLSearchParams();
  params.set("date", state.date);

  FILTER_CATEGORIES.forEach((category) => {
    state.filters[category].forEach((value) => params.append(category, value));
  });

  if (state.filters.only_magdalenka) {
    params.set("only_magdalenka", "1");
  }

  const query = params.toString();
  const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}`;
  window.history.replaceState(null, "", nextUrl);
}
