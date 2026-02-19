import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

import { DayTabs } from "./components/DayTabs";
import { ScheduleBoard } from "./components/ScheduleBoard";
import { WeekNavigator } from "./components/WeekNavigator";
import { fetchMeta, fetchWeekSchedule } from "./lib/api";
import { coerceToWorkday, getTodayInTimezone, shiftDate, startOfWeek } from "./lib/date";
import { createDefaultFilters, readUrlState, writeUrlState } from "./lib/urlState";
import type { UrlState } from "./types";

const FALLBACK_TIMEZONE = "Europe/Warsaw";

export default function App() {
  const sanitizeState = (value: UrlState): UrlState => ({
    ...value,
    filters: {
      ...createDefaultFilters(),
      only_magdalenka: value.filters.only_magdalenka,
    },
  });

  const initialDate = coerceToWorkday(getTodayInTimezone(FALLBACK_TIMEZONE));
  const [state, setState] = useState<UrlState>(() => sanitizeState(readUrlState(initialDate)));

  useEffect(() => {
    const onPopState = () => {
      setState(sanitizeState(readUrlState(initialDate)));
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

  const magdalenkaEnabled = useMemo(() => state.filters.only_magdalenka, [state.filters.only_magdalenka]);

  const updateDate = (date: string) => {
    if (!date) {
      return;
    }

    setState((previous) => ({ ...previous, date }));
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
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_15%_12%,rgba(106,126,112,0.12),transparent_44%),radial-gradient(circle_at_88%_16%,rgba(141,160,177,0.14),transparent_50%),linear-gradient(180deg,#f4f1e9_0%,#f7f6f1_46%,#f1f4f4_100%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-25 [background-image:linear-gradient(90deg,rgba(18,17,15,0.035)_1px,transparent_1px),linear-gradient(rgba(18,17,15,0.035)_1px,transparent_1px)] [background-size:52px_52px]" />

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

        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="space-y-4"
        >
          <div className="space-y-3 rounded-3xl border border-black/10 bg-white/75 p-3 shadow-panel backdrop-blur md:p-4">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-clay" />
                <p className="font-heading text-xl font-bold tracking-tight text-ink">Widok dnia</p>
              </div>
              <button
                type="button"
                onClick={toggleOnlyMagdalenka}
                className={`inline-flex w-full items-center justify-between rounded-xl border px-3 py-2 text-sm font-semibold md:w-auto ${
                  magdalenkaEnabled
                    ? "border-clay bg-clay/10 text-clay"
                    : "border-black/15 bg-white text-black/70 hover:bg-black/5"
                }`}
              >
                <span>Tylko grupy Magdalenki</span>
                <span className={`h-2.5 w-2.5 rounded-full ${magdalenkaEnabled ? "bg-clay" : "bg-black/25"}`} />
              </button>
            </div>
            <div className="rounded-xl border border-black/10 bg-white/72 px-3 py-2 text-xs leading-5 text-black/65">
              <span className="font-semibold text-black/72">Legenda przelacznika:</span>{" "}
              pokazywane sa tylko grupy Magdalenki: caly rok (<code>---</code>, <code>rok</code>, <code>wszyscy</code>),
              grupa <code>11*</code> (np. <code>11</code>, <code>11A</code>) oraz <code>D</code> bez cyfr.
            </div>
            <div className="rounded-2xl border border-black/10 bg-white/80 p-2.5">
              <DayTabs weekStart={weekStart} selectedDate={state.date} onSelectDate={updateDate} />
            </div>
          </div>

          {(metaQuery.isLoading || weekQuery.isLoading) && (
            <div className="rounded-2xl border border-black/10 bg-white/75 p-6 text-sm font-semibold text-black/55 shadow-panel">
              Ladowanie planu...
            </div>
          )}

          {!weekQuery.isLoading && <ScheduleBoard day={daySchedule} timezone={timezone} />}
        </motion.section>

        <footer className="pb-2 pt-1 text-center text-xs font-medium tracking-wide text-black/45">
          Made with love❤️.
        </footer>
      </main>
    </div>
  );
}
