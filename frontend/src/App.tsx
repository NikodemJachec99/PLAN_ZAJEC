import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";

import { DayTabs } from "./components/DayTabs";
import { FilterPanel } from "./components/FilterPanel";
import { ScheduleBoard } from "./components/ScheduleBoard";
import { WeekNavigator } from "./components/WeekNavigator";
import { fetchMeta, fetchWeekSchedule } from "./lib/api";
import { coerceToWorkday, getTodayInTimezone, shiftDate, startOfWeek } from "./lib/date";
import { FILTER_CATEGORIES, createDefaultFilters, readUrlState, writeUrlState } from "./lib/urlState";
import type { FilterCategory, UrlState } from "./types";

const FALLBACK_TIMEZONE = "Europe/Warsaw";

export default function App() {
  const initialDate = coerceToWorkday(getTodayInTimezone(FALLBACK_TIMEZONE));
  const [state, setState] = useState<UrlState>(() => readUrlState(initialDate));

  useEffect(() => {
    const onPopState = () => {
      setState(readUrlState(initialDate));
    };

    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [initialDate]);

  useEffect(() => {
    writeUrlState(state);
  }, [state]);

  const metaQuery = useQuery({
    queryKey: ["meta"],
    queryFn: fetchMeta,
    refetchInterval: 60_000,
  });

  const timezone = metaQuery.data?.timezone ?? FALLBACK_TIMEZONE;

  const weekQuery = useQuery({
    queryKey: ["week", state.date, state.filters],
    queryFn: () => fetchWeekSchedule(state.date, state.filters),
    refetchInterval: 60_000,
    enabled: Boolean(state.date),
  });

  const weekStart = weekQuery.data?.week_start ?? startOfWeek(state.date);
  const daySchedule = weekQuery.data?.days.find((day) => day.date === state.date) ?? weekQuery.data?.days[0];

  const errorMessage = metaQuery.error instanceof Error
    ? metaQuery.error.message
    : weekQuery.error instanceof Error
      ? weekQuery.error.message
      : null;

  const selectedFiltersCount = useMemo(() => {
    const categoryCount = FILTER_CATEGORIES.reduce((total, key) => total + state.filters[key].length, 0);
    return categoryCount + (state.filters.only_magdalenka ? 1 : 0);
  }, [state.filters]);

  const updateDate = (date: string) => {
    if (!date) {
      return;
    }

    setState((previous) => ({ ...previous, date }));
  };

  const toggleFilterValue = (category: FilterCategory, value: string) => {
    setState((previous) => {
      const selected = previous.filters[category];
      const nextValues = selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value];

      return {
        ...previous,
        filters: {
          ...previous.filters,
          [category]: nextValues,
        },
      };
    });
  };

  const clearCategory = (category: FilterCategory) => {
    setState((previous) => ({
      ...previous,
      filters: {
        ...previous.filters,
        [category]: [],
      },
    }));
  };

  const clearAllFilters = () => {
    setState((previous) => ({
      ...previous,
      filters: createDefaultFilters(),
    }));
  };

  const toggleOnlyMagdalenka = () => {
    setState((previous) => ({
      ...previous,
      filters: {
        ...previous.filters,
        only_magdalenka: !previous.filters.only_magdalenka,
      },
    }));
  };

  const goToday = () => {
    updateDate(coerceToWorkday(getTodayInTimezone(timezone)));
  };

  const goPrevWeek = () => {
    updateDate(shiftDate(state.date, -7));
  };

  const goNextWeek = () => {
    updateDate(shiftDate(state.date, 7));
  };

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-linen text-ink">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_15%_15%,rgba(204,92,45,0.18),transparent_45%),radial-gradient(circle_at_85%_10%,rgba(53,95,72,0.2),transparent_40%),radial-gradient(circle_at_90%_85%,rgba(95,157,200,0.2),transparent_50%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-40 [background-image:linear-gradient(90deg,rgba(18,17,15,0.04)_1px,transparent_1px),linear-gradient(rgba(18,17,15,0.04)_1px,transparent_1px)] [background-size:38px_38px]" />

      <main className="relative mx-auto flex w-full max-w-[1400px] flex-col gap-5 px-4 py-4 md:px-6 md:py-6">
        <WeekNavigator
          selectedDate={state.date}
          weekStart={weekStart}
          minDate={metaQuery.data?.min_date}
          maxDate={metaQuery.data?.max_date}
          onPrevWeek={goPrevWeek}
          onNextWeek={goNextWeek}
          onToday={goToday}
          onDateChange={updateDate}
        />

        {errorMessage && (
          <div className="rounded-2xl border border-red-300 bg-red-100/80 px-4 py-3 text-sm font-semibold text-red-700">
            Nie udalo sie pobrac danych: {errorMessage}
          </div>
        )}

        <div className="grid items-start gap-4 lg:grid-cols-[320px_1fr]">
          <FilterPanel
            options={metaQuery.data?.filters}
            filters={state.filters}
            onToggleValue={toggleFilterValue}
            onClearCategory={clearCategory}
            onToggleOnlyMagdalenka={toggleOnlyMagdalenka}
            onClearAll={clearAllFilters}
          />

          <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="space-y-3"
          >
            <div className="flex flex-col gap-2 rounded-2xl border border-black/10 bg-white/80 p-3 shadow-panel">
              <div className="flex items-center justify-between">
                <p className="font-heading text-xl font-bold tracking-tight text-ink">Widok dnia</p>
                <p className="text-xs font-semibold text-black/55">Aktywne filtry: {selectedFiltersCount}</p>
              </div>
              <DayTabs weekStart={weekStart} selectedDate={state.date} onSelectDate={updateDate} />
            </div>

            {(metaQuery.isLoading || weekQuery.isLoading) && (
              <div className="rounded-2xl border border-black/10 bg-white/75 p-6 text-sm font-semibold text-black/55 shadow-panel">
                Ladowanie planu...
              </div>
            )}

            {!weekQuery.isLoading && <ScheduleBoard day={daySchedule} timezone={timezone} />}
          </motion.section>
        </div>
      </main>
    </div>
  );
}
