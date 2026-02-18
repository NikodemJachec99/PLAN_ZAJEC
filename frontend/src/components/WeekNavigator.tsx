import { CalendarDays, ChevronLeft, ChevronRight, Crosshair } from "lucide-react";

import { polishDateLabel, weekRangeLabel } from "../lib/date";

interface WeekNavigatorProps {
  selectedDate: string;
  weekStart: string;
  minDate?: string | null;
  maxDate?: string | null;
  onPrevWeek: () => void;
  onNextWeek: () => void;
  onToday: () => void;
  onDateChange: (date: string) => void;
}

export function WeekNavigator({
  selectedDate,
  weekStart,
  minDate,
  maxDate,
  onPrevWeek,
  onNextWeek,
  onToday,
  onDateChange,
}: WeekNavigatorProps) {
  return (
    <section className="rounded-3xl border border-black/10 bg-gradient-to-br from-white via-sand to-sky p-4 shadow-panel">
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-ink">Plan Zajec</h1>
          <p className="mt-1 text-sm text-black/65">{polishDateLabel(selectedDate)} - tydzien {weekRangeLabel(weekStart)}</p>
        </div>

        <label className="inline-flex items-center gap-2 rounded-xl border border-black/15 bg-white/70 px-3 py-2 text-sm font-semibold text-ink">
          <CalendarDays className="h-4 w-4 text-moss" />
          <input
            type="date"
            className="bg-transparent text-sm font-semibold text-ink outline-none"
            value={selectedDate}
            min={minDate ?? undefined}
            max={maxDate ?? undefined}
            onChange={(event) => onDateChange(event.target.value)}
          />
        </label>
      </div>

      <div className="grid grid-cols-3 gap-2 md:grid-cols-4">
        <button
          type="button"
          onClick={onPrevWeek}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-black/15 bg-white px-3 py-2 text-sm font-semibold text-black/75 hover:bg-black/5"
        >
          <ChevronLeft className="h-4 w-4" /> Poprzedni
        </button>
        <button
          type="button"
          onClick={onToday}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-clay/40 bg-clay/10 px-3 py-2 text-sm font-semibold text-clay hover:bg-clay/20"
        >
          <Crosshair className="h-4 w-4" /> Dzis
        </button>
        <button
          type="button"
          onClick={onNextWeek}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-black/15 bg-white px-3 py-2 text-sm font-semibold text-black/75 hover:bg-black/5"
        >
          Nastepny <ChevronRight className="h-4 w-4" />
        </button>
        <div className="col-span-3 flex items-center justify-end rounded-xl border border-black/10 bg-white/70 px-3 py-2 text-xs font-semibold text-black/65 md:col-span-1">
          Auto refresh: 60s
        </div>
      </div>
    </section>
  );
}
