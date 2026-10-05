import type { Item } from "../lib/model";
import { isoDay, isWeekend, MON, mondayOf, parseDay, shift } from "../lib/time";

interface MonthViewProps {
  byDay: Map<string, Item[]>;
  months: string[]; // "YYYY-MM"
  today: string;
  showWeekends: boolean;
  legend: { short: string; color: string }[];
  onOpenDay: (day: string) => void;
}

const WEEK_LABELS = ["pn", "wt", "śr", "czw", "pt", "sb", "nd"];

export function MonthView({ byDay, months, today, showWeekends, legend, onOpenDay }: MonthViewProps) {
  const columns = showWeekends ? 7 : 5;
  return (
    <section className="flex flex-col gap-3.5">
      <div className="px-1 text-sm text-muted">Kliknij dzień, aby zobaczyć szczegóły.</div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,300px),1fr))] gap-3.5">
        {months.map((month) => {
          const first = parseDay(`${month}-01`);
          const last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
          const cells: Date[] = [];
          for (let day = mondayOf(first); day <= last || day.getDay() !== 1; day = shift(day, 1)) {
            if (!showWeekends && isWeekend(day)) continue;
            cells.push(day);
          }
          return (
            <div key={month} className="flex flex-col gap-2.5 rounded-[20px] border border-line bg-linen p-4">
              <div className="font-heading text-[19px] font-extrabold capitalize">
                {MON[first.getMonth()]} {first.getFullYear()}
              </div>
              <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
                {WEEK_LABELS.slice(0, columns).map((label) => (
                  <div key={label} className="text-center text-[11px] font-extrabold uppercase text-subtle">
                    {label}
                  </div>
                ))}
                {cells.map((day) => {
                  const key = isoDay(day);
                  const inMonth = day.getMonth() === first.getMonth();
                  const items = byDay.get(key);
                  const colors = items ? [...new Set(items.map((item) => item.pal.dot))].slice(0, 4) : [];
                  const isToday = key === today;
                  return (
                    <button
                      key={key}
                      type="button"
                      disabled={!inMonth}
                      onClick={() => inMonth && onOpenDay(key)}
                      aria-label={`${day.getDate()} ${MON[day.getMonth()]}${items ? `, ${items.length} zajęć` : ""}`}
                      className="flex h-[50px] flex-col items-center justify-center gap-[5px] rounded-[10px] border-2 p-0"
                      style={{
                        visibility: inMonth ? "visible" : "hidden",
                        borderColor: isToday ? "#cc5c2d" : "transparent",
                        background: isToday ? "#f3dccd" : items && inMonth ? "#f4efe3" : "transparent",
                        color: key < today ? "#a39b8a" : "#12110f",
                        cursor: items ? "pointer" : "default",
                      }}
                    >
                      <span className="text-sm font-extrabold leading-none">{day.getDate()}</span>
                      <span className="flex h-1.5 gap-[3px]">
                        {inMonth && colors.map((color) => <span key={color} className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-2 px-1">
        {legend.map((item) => (
          <div key={item.short} className="flex items-center gap-2 text-[13px] font-semibold">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: item.color }} />
            {item.short}
          </div>
        ))}
      </div>
    </section>
  );
}
