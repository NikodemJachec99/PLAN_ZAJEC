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
    <div className="grid grid-cols-5 gap-2">
      {weekdays.map((date) => (
        <button
          key={date}
          type="button"
          onClick={() => onSelectDate(date)}
          className={cn(
            "rounded-xl border px-3 py-2 text-sm font-semibold transition",
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
