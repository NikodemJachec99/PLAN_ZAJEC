import { motion } from "framer-motion";

import { getNowMinutesInTimezone } from "../lib/date";
import type { DaySchedule, ScheduleEvent } from "../types";

const PX_PER_MIN = 65 / 60;

function colorHue(color: string): number {
  const match = color.match(/hsl\((\d+)/i);
  if (!match) {
    return 210;
  }
  return Number(match[1]);
}

function eventBackground(color: string): string {
  const hue = colorHue(color);
  return `hsl(${hue} 94% 92%)`;
}

function eventBorder(color: string): string {
  const hue = colorHue(color);
  return `hsl(${hue} 68% 42%)`;
}

function buildLegend(events: ScheduleEvent[]): Array<{ subject: string; color: string }> {
  const seen = new Map<string, string>();
  events.forEach((event) => {
    const subject = event.subject.trim();
    if (subject && !seen.has(subject)) {
      seen.set(subject, event.color_hsl);
    }
  });

  return Array.from(seen.entries()).map(([subject, color]) => ({ subject, color }));
}

interface ScheduleBoardProps {
  day?: DaySchedule;
  timezone: string;
}

export function ScheduleBoard({ day, timezone }: ScheduleBoardProps) {
  if (!day) {
    return (
      <div className="rounded-2xl border border-black/10 bg-white/80 p-6 text-sm text-black/60 shadow-panel">
        Brak danych dla wybranego tygodnia.
      </div>
    );
  }

  const rangeStart = day.range_start_min;
  const rangeEnd = day.range_end_min;
  const height = Math.max(60, (rangeEnd - rangeStart) * PX_PER_MIN);
  const firstHour = Math.ceil(rangeStart / 60);
  const lastHour = Math.floor(rangeEnd / 60);

  const ticks = Array.from({ length: Math.max(0, lastHour - firstHour + 1) }, (_, index) => firstHour + index);
  const legend = buildLegend(day.events);

  const now = getNowMinutesInTimezone(timezone);
  const showNow = now.isoDate === day.date;
  const nowTop = Math.max(0, Math.min(height, (now.minutes - rangeStart) * PX_PER_MIN));

  return (
    <section className="space-y-3">
      {legend.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {legend.map((item) => (
            <span
              key={item.subject}
              className="rounded-full border px-3 py-1 text-xs font-semibold text-ink"
              style={{
                backgroundColor: eventBackground(item.color),
                borderColor: eventBorder(item.color),
              }}
            >
              {item.subject}
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-[60px_1fr] gap-3">
        <div className="relative rounded-xl border border-black/10 bg-white/70" style={{ height }}>
          {ticks.map((hour) => {
            const top = (hour * 60 - rangeStart) * PX_PER_MIN;
            return (
              <div key={`tick-label-${hour}`} className="absolute left-0 right-1 -translate-y-1/2 text-right text-[11px] font-semibold text-black/45" style={{ top }}>
                {`${hour.toString().padStart(2, "0")}:00`}
              </div>
            );
          })}
        </div>

        <div className="relative overflow-hidden rounded-2xl border border-black/10 bg-white/85 shadow-panel" style={{ height }}>
          {ticks.map((hour) => {
            const top = (hour * 60 - rangeStart) * PX_PER_MIN;
            return (
              <div
                key={`tick-line-${hour}`}
                className="absolute left-0 right-0 border-t border-dashed border-black/10"
                style={{ top }}
              />
            );
          })}

          {showNow && (
            <>
              <div className="absolute left-0 right-0 border-t-2 border-red-500" style={{ top: nowTop }} />
              <div className="absolute right-2 -translate-y-full rounded bg-red-500 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white" style={{ top: nowTop }}>
                Teraz
              </div>
            </>
          )}

          {day.events.length === 0 && (
            <div className="flex h-full items-center justify-center text-sm font-semibold text-black/45">Brak zajec</div>
          )}

          {day.events.map((event, index) => {
            const width = 100 / Math.max(1, event.layout_cols_total);
            const left = event.layout_col * width;
            const top = (event.start_min - rangeStart) * PX_PER_MIN;
            const blockHeight = Math.max(38, (event.end_min - event.start_min) * PX_PER_MIN);

            return (
              <motion.article
                key={event.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, delay: Math.min(index * 0.02, 0.25) }}
                className="absolute overflow-hidden rounded-xl border px-2.5 py-2"
                style={{
                  top,
                  height: blockHeight,
                  left: `calc(${left}% + 2px)`,
                  width: `calc(${width}% - 6px)`,
                  backgroundColor: eventBackground(event.color_hsl),
                  borderColor: eventBorder(event.color_hsl),
                }}
              >
                <p className="truncate text-sm font-extrabold text-ink">{event.subject || "Bez nazwy"}</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  <span className="rounded-full border border-black/15 bg-white/80 px-2 py-0.5 text-[11px] font-semibold text-black/70">
                    {event.start_time}-{event.end_time}
                  </span>
                  {event.room && (
                    <span className="rounded-full border border-black/15 bg-white/80 px-2 py-0.5 text-[11px] font-semibold text-black/70">
                      Sala {event.room}
                    </span>
                  )}
                  {event.group && (
                    <span className="rounded-full border border-black/15 bg-white/80 px-2 py-0.5 text-[11px] font-semibold text-black/70">
                      Gr {event.group}
                    </span>
                  )}
                </div>
                {event.instructor && <p className="mt-1 truncate text-[11px] text-black/70">{event.instructor}</p>}
              </motion.article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
