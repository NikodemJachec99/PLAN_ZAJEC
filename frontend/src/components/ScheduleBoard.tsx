import { motion } from "framer-motion";

import { getNowMinutesInTimezone } from "../lib/date";
import type { DaySchedule, ScheduleEvent } from "../types";

const HOUR_HEIGHT_PX = 74;
const PX_PER_MIN = HOUR_HEIGHT_PX / 60;

function colorHue(color: string): number {
  const match = color.match(/hsl\((\d+)/i);
  if (!match) {
    return 210;
  }
  return Number(match[1]);
}

function eventBackground(color: string): string {
  const hue = colorHue(color);
  return `hsl(${hue} 42% 97%)`;
}

function eventBorder(color: string): string {
  const hue = colorHue(color);
  return `hsl(${hue} 52% 45%)`;
}

function eventAccent(color: string): string {
  const hue = colorHue(color);
  const hue2 = (hue + 18) % 360;
  return `linear-gradient(180deg, hsl(${hue} 78% 58%), hsl(${hue2} 73% 52%))`;
}

function minutesToTimeLabel(total: number): string {
  const hours = Math.floor(total / 60)
    .toString()
    .padStart(2, "0");
  const minutes = Math.floor(total % 60)
    .toString()
    .padStart(2, "0");
  return `${hours}:${minutes}`;
}

function durationLabel(startMin: number, endMin: number): string {
  const diff = Math.max(0, endMin - startMin);
  const hours = Math.floor(diff / 60);
  const minutes = diff % 60;

  if (hours > 0 && minutes > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (hours > 0) {
    return `${hours}h`;
  }
  return `${minutes}m`;
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

function isEventLive(nowMinutes: number, event: ScheduleEvent): boolean {
  return nowMinutes >= event.start_min && nowMinutes < event.end_min;
}

interface ScheduleBoardProps {
  day?: DaySchedule;
  timezone: string;
}

export function ScheduleBoard({ day, timezone }: ScheduleBoardProps) {
  if (!day) {
    return (
      <div className="rounded-3xl border border-black/10 bg-white/80 p-6 text-sm text-black/60 shadow-panel">
        Brak danych dla wybranego tygodnia.
      </div>
    );
  }

  const sortedEvents = [...day.events].sort((a, b) => a.start_min - b.start_min || a.end_min - b.end_min);
  const legend = buildLegend(sortedEvents);

  const rangeStart = day.range_start_min;
  const rangeEnd = day.range_end_min;
  const duration = Math.max(60, rangeEnd - rangeStart);
  const canvasHeight = duration * PX_PER_MIN;

  const now = getNowMinutesInTimezone(timezone);
  const showNow = now.isoDate === day.date;
  const nowTop = (now.minutes - rangeStart) * PX_PER_MIN;
  const nowInsideCanvas = showNow && nowTop >= 0 && nowTop <= canvasHeight;

  const firstHour = Math.ceil(rangeStart / 60);
  const lastHour = Math.floor(rangeEnd / 60);
  const ticks = Array.from({ length: Math.max(0, lastHour - firstHour + 1) }, (_, idx) => firstHour + idx);

  return (
    <section className="space-y-4">
      <div className="rounded-3xl border border-black/10 bg-white/82 p-4 shadow-panel">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-black/45">Plan dnia</p>
            <h3 className="font-heading text-2xl font-extrabold leading-tight text-ink">
              {sortedEvents.length === 0 ? "Brak zajec" : `${sortedEvents.length} zajec`}
            </h3>
          </div>

          <div className="flex flex-wrap gap-2 text-xs font-semibold">
            <span className="rounded-full border border-black/15 bg-white px-3 py-1.5 text-black/70">Data: {day.date}</span>
            <span className="rounded-full border border-black/15 bg-white px-3 py-1.5 text-black/70">
              Zakres: {minutesToTimeLabel(rangeStart)}-{minutesToTimeLabel(rangeEnd)}
            </span>
          </div>
        </div>
      </div>

      {legend.length > 0 && (
        <div className="flex snap-x gap-2 overflow-x-auto pb-1">
          {legend.map((item) => (
            <span
              key={item.subject}
              className="shrink-0 rounded-full border px-3 py-1.5 text-xs font-bold text-ink"
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

      <div className="overflow-x-auto">
        <div className="grid min-w-[320px] grid-cols-[50px_1fr] gap-2 rounded-3xl border border-black/10 bg-white/84 p-2 shadow-panel md:grid-cols-[62px_1fr] md:gap-3 md:p-3">
          <div className="relative rounded-2xl border border-black/10 bg-white/75" style={{ height: `${canvasHeight}px` }}>
            {ticks.map((hour) => {
              const top = (hour * 60 - rangeStart) * PX_PER_MIN;
              return (
                <div
                  key={`tick-label-${hour}`}
                  className="absolute left-0 right-1 -translate-y-1/2 text-right text-[10px] font-semibold text-black/42 md:text-[11px]"
                  style={{ top: `${top}px` }}
                >
                  {hour.toString().padStart(2, "0")}:00
                </div>
              );
            })}
          </div>

          <div className="relative overflow-hidden rounded-2xl border border-black/10 bg-white" style={{ height: `${canvasHeight}px` }}>
            <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(18,17,15,0.022)_0%,rgba(18,17,15,0)_100%)]" />

            {ticks.map((hour) => {
              const top = (hour * 60 - rangeStart) * PX_PER_MIN;
              return (
                <div
                  key={`tick-line-${hour}`}
                  className="absolute left-0 right-0 border-t border-dashed border-black/10"
                  style={{ top: `${top}px` }}
                />
              );
            })}

            {nowInsideCanvas && (
              <>
                <div className="absolute left-0 right-0 border-t-2 border-red-500" style={{ top: `${nowTop}px` }} />
                <div className="absolute right-2 -translate-y-full rounded bg-red-500 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white" style={{ top: `${nowTop}px` }}>
                  Teraz {minutesToTimeLabel(now.minutes)}
                </div>
              </>
            )}

            {sortedEvents.length === 0 && (
              <div className="flex h-full items-center justify-center px-6 text-center text-sm font-semibold text-black/48">
                Brak zajec w tym dniu.
              </div>
            )}

            {sortedEvents.map((event, index) => {
              const totalCols = Math.max(1, event.layout_cols_total);
              const width = 100 / totalCols;
              const left = event.layout_col * width;
              const top = (event.start_min - rangeStart) * PX_PER_MIN;
              const rawHeight = (event.end_min - event.start_min) * PX_PER_MIN;
              const visualInset = rawHeight > 32 ? 1 : 0;
              const blockTop = top + visualInset;
              const blockHeight = Math.max(22, rawHeight - visualInset * 2);
              const isTiny = blockHeight < 58;
              const live = showNow && isEventLive(now.minutes, event);

              return (
                <motion.article
                  key={event.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18, delay: Math.min(index * 0.02, 0.2) }}
                  className="absolute overflow-hidden rounded-2xl border border-black/12 bg-white/95 shadow-[0_12px_24px_-20px_rgba(0,0,0,0.35)]"
                  style={{
                    top: `${blockTop}px`,
                    height: `${blockHeight}px`,
                    left: `calc(${left}% + 3px)`,
                    width: `calc(${width}% - 6px)`,
                    borderColor: eventBorder(event.color_hsl),
                    backgroundColor: eventBackground(event.color_hsl),
                  }}
                >
                  <div className="absolute inset-y-0 left-0 w-1.5" style={{ backgroundImage: eventAccent(event.color_hsl) }} />

                  <div className="h-full overflow-y-auto overflow-x-hidden px-3 pb-2 pt-2 pl-4 pr-2">
                    <div className="flex items-start justify-between gap-1.5">
                      <p className={`${isTiny ? "text-[12px] leading-4" : "text-[13px] leading-4 md:text-sm md:leading-5"} break-words pr-2 font-extrabold text-ink`}>
                        {event.subject || "Bez nazwy"}
                      </p>
                      {live && <span className="rounded-full bg-red-500 px-2 py-0.5 text-[10px] font-bold text-white">Trwa teraz</span>}
                    </div>

                    <div className={`${isTiny ? "mt-1" : "mt-1.5"} flex flex-wrap gap-1.5`}>
                      <span className="rounded-full border border-black/15 bg-white/80 px-2 py-0.5 text-[10px] font-bold text-black/75 md:text-[11px]">
                        {event.start_time}-{event.end_time}
                      </span>
                      <span className="rounded-full border border-black/15 bg-white/80 px-2 py-0.5 text-[10px] font-semibold text-black/68 md:text-[11px]">
                        {durationLabel(event.start_min, event.end_min)}
                      </span>
                    </div>

                    <p className="mt-1.5 text-[11px] leading-4 text-black/68 md:text-xs">
                      <span className="font-semibold text-black/76">Prowadzacy: </span>
                      <span>{event.instructor || "-"}</span>
                    </p>

                    <div className="mt-1 flex flex-wrap gap-1">
                      <span className="rounded-full border border-black/12 bg-white/70 px-2 py-0.5 text-[10px] font-semibold text-black/70">
                        Sala: {event.room || "-"}
                      </span>
                      <span className="rounded-full border border-black/12 bg-white/70 px-2 py-0.5 text-[10px] font-semibold text-black/70">
                        Grupa: {event.group || "-"}
                      </span>
                      <span className="rounded-full border border-black/12 bg-white/70 px-2 py-0.5 text-[10px] font-semibold text-black/70">
                        Typ: {event.type || "-"}
                      </span>
                    </div>

                    <div className="mt-1 space-y-0.5">
                      <p className="text-[10px] text-black/60">
                        <span className="font-semibold text-black/72">Oddzial: </span>
                        <span>{event.oddzial || "-"}</span>
                      </p>
                      <p className="text-[10px] text-black/60">
                        <span className="font-semibold text-black/72">Zrodlo: </span>
                        <span>{event.source || "-"}</span>
                      </p>
                    </div>
                  </div>
                </motion.article>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
