import type { Item } from "../lib/model";
import { MON, parseDay, plural, WD } from "../lib/time";
import { CancelledBadge } from "./EventBits";

interface ListViewProps {
  byDay: Map<string, Item[]>;
  today: string;
  showPast: boolean;
  onOpenDay: (day: string) => void;
}

export function ListView({ byDay, today, showPast, onOpenDay }: ListViewProps) {
  const days = [...byDay.keys()].sort().filter((day) => showPast || day >= today);
  const months = new Map<string, string[]>();
  days.forEach((day) => {
    const key = day.slice(0, 7);
    months.set(key, [...(months.get(key) ?? []), day]);
  });

  return (
    <section className="flex flex-col gap-5 sm:gap-7">
      {months.size === 0 && (
        <div className="rounded-[20px] border border-dashed border-rule bg-linen p-8 text-center text-muted">
          Wszystkie zajęcia w tym semestrze już się odbyły.
        </div>
      )}
      {[...months.entries()].map(([month, monthDays]) => {
        const first = parseDay(`${month}-01`);
        return (
          <div key={month} className="flex flex-col gap-2.5">
            <div className="flex items-baseline gap-3 px-1">
              <h3 className="m-0 font-heading text-[22px] font-extrabold capitalize sm:text-[26px]">
                {MON[first.getMonth()]} {first.getFullYear()}
              </h3>
              <span className="text-xs text-subtle sm:text-sm">
                {monthDays.length} {plural(monthDays.length, "dzień", "dni", "dni")} z zajęciami
              </span>
            </div>
            {monthDays.map((day) => {
              const date = parseDay(day);
              const isToday = day === today;
              return (
                <div
                  key={day}
                  className="grid grid-cols-[46px_minmax(0,1fr)] gap-2.5 rounded-2xl border border-line bg-linen p-2.5 sm:grid-cols-[64px_minmax(0,1fr)] sm:gap-3.5 sm:rounded-[20px] sm:p-3.5"
                  style={{ opacity: day < today ? 0.5 : 1 }}
                >
                  <button
                    type="button"
                    onClick={() => onOpenDay(day)}
                    className="flex cursor-pointer flex-col items-center justify-center self-start rounded-xl border-0 py-2 sm:rounded-[14px] sm:py-2.5"
                    style={{ background: isToday ? "#cc5c2d" : "#f4efe3", color: isToday ? "#fffaf0" : "#12110f" }}
                  >
                    <span className="font-heading text-[22px] font-extrabold leading-none sm:text-[28px]">{date.getDate()}</span>
                    <span className="text-[10px] font-extrabold uppercase tracking-[0.06em] sm:text-xs">{WD[date.getDay()]}</span>
                  </button>
                  <div className="flex min-w-0 flex-col gap-2 sm:gap-2.5">
                    {(byDay.get(day) ?? []).map((item) => (
                      <div key={item.e.id} className="grid grid-cols-[72px_minmax(0,1fr)] items-start gap-x-2 gap-y-1 sm:grid-cols-[minmax(96px,auto)_minmax(0,1fr)] sm:gap-x-3.5">
                        <div className="flex flex-col gap-1">
                          <span className="tabular text-[13px] font-extrabold leading-tight sm:whitespace-nowrap sm:text-[15px]">{item.time}</span>
                          <span
                            className="self-start whitespace-nowrap rounded-full px-2 py-[3px] text-[10px] font-extrabold text-linen sm:text-[11px]"
                            style={{ background: item.modeBg }}
                          >
                            {item.modeShort}
                          </span>
                        </div>
                        <div className="flex min-w-0 flex-col gap-[3px]">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="h-2.5 w-2.5 flex-none rounded-[3px]" style={{ background: item.pal.dot }} />
                            <span
                              className="text-pretty text-sm font-extrabold leading-[1.3] sm:text-[15px]"
                              style={{ textDecoration: item.e.cancelled ? "line-through" : undefined }}
                            >
                              {item.title}
                            </span>
                            <span className="rounded-full px-2 py-0.5 text-[11px] font-extrabold sm:text-xs" style={{ background: item.pal.bg, color: item.pal.c }}>
                              {item.type}
                            </span>
                            <CancelledBadge item={item} />
                          </div>
                          <div className="text-pretty text-[13px] leading-[1.4] text-body2 sm:text-sm sm:leading-[1.45]">
                            <strong className="font-bold text-ink">{item.where}</strong> {item.place}
                          </div>
                          <div className="text-xs text-subtle sm:text-[13px]">
                            {item.who} {item.note ? `· ${item.note}` : ""}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </section>
  );
}
