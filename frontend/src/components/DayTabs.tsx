import { dayShortLabel, shiftDate } from "../lib/date";
import { cn } from "../lib/cn";

interface DayTabsProps {
  weekStart: string;
  selectedDate: string;
  onSelectDate: (date: string) => void;
}

export function DayTabs({ weekStart, selectedDate, onSelectDate }: DayTabsProps) {
  const weekdays = Array.from({ length: 5 }, (_, index) => shiftDate(weekStart, index));

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 md:grid md:grid-cols-5 md:overflow-visible">
      {weekdays.map((date) => (
        <button
          key={date}
          type="button"
          onClick={() => onSelectDate(date)}
          className={cn(
            "shrink-0 rounded-xl border px-4 py-2.5 text-sm font-semibold transition md:px-3 md:py-2",
            selectedDate === date
              ? "border-moss bg-moss text-white shadow-panel"
              : "border-black/15 bg-white/85 text-black/70 hover:bg-white",
          )}
        >
          {dayShortLabel(date)}
        </button>
      ))}
    </div>
  );
}
