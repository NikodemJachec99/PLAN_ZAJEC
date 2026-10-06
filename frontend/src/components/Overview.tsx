import { useState } from "react";

import type { Item } from "../lib/model";
import { dayLong, fmtHours, parseDay } from "../lib/time";

export interface Stat {
  short: string;
  color: string;
  hours: number;
}

interface OverviewProps {
  next?: Item;
  nextLive: boolean;
  today: string;
  groupLabel: string;
  stats: Stat[];
  hoursOnsite: number;
  hoursRemote: number;
  compact?: boolean;
  /** Phones render the "next class" card at the top and the hours card below the plan. */
  show?: "both" | "next" | "hours";
}

const COMPACT_STATS = 4;

function relative(date: string, today: string, live: boolean): string {
  if (live) return "teraz";
  const diff = Math.round((parseDay(date).getTime() - parseDay(today).getTime()) / 864e5);
  if (diff === 0) return "dziś";
  if (diff === 1) return "jutro";
  return `za ${diff} dni`;
}

export function Overview({
  next,
  nextLive,
  today,
  groupLabel,
  stats,
  hoursOnsite,
  hoursRemote,
  compact = false,
  show = "both",
}: OverviewProps) {
  const [allStats, setAllStats] = useState(false);
  const max = Math.max(1, ...stats.map((stat) => stat.hours));
  const shown = compact && !allStats ? stats.slice(0, COMPACT_STATS) : stats;
  return (
    <section className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,340px),1fr))] gap-3 sm:gap-4">
      {show !== "hours" && (
        <div className="flex min-w-0 flex-col gap-3 rounded-3xl bg-ink p-4 text-linen sm:gap-[18px] sm:p-[26px]">
          <div className="flex items-center justify-between gap-2.5">
            <div className="text-[13px] font-bold uppercase tracking-[0.08em] text-soft max-sm:text-[11px] max-sm:tracking-[0.05em]">
              Najbliższe zajęcia · {groupLabel}
            </div>
            <div className="whitespace-nowrap rounded-full bg-clay px-3 py-1.5 text-[13px] font-extrabold text-linen max-sm:px-2.5 max-sm:py-1 max-sm:text-xs">
              {next ? relative(next.e.date, today, nextLive) : "✓"}
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <div className="font-heading text-[clamp(22px,4vw,40px)] font-extrabold leading-[1.02] tracking-[-0.02em]">
              {next ? dayLong(next.e.date) : "Koniec semestru"}
            </div>
            <div className="text-base font-semibold text-stone sm:text-lg">{next ? next.time : ""}</div>
          </div>
          <div className="flex flex-col gap-2 border-t border-dusk pt-3 sm:gap-2.5 sm:pt-4">
            <div className="flex flex-wrap gap-1.5">
              <span className="rounded-full px-2.5 py-[5px] text-xs font-extrabold text-linen" style={{ background: next ? next.modeBg : "#3a362f" }}>
                {next ? next.modeLabel : "—"}
              </span>
              <span className="rounded-full bg-coal px-2.5 py-[5px] text-xs font-extrabold text-stone">{next ? next.type : "—"}</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="h-3 w-3 flex-none rounded" style={{ background: next ? next.pal.dot : "#c9bfa9" }} />
              <span className="text-pretty text-[15px] font-bold sm:text-[17px]">{next ? next.title : "Brak kolejnych zajęć"}</span>
            </div>
            {next && (
              <div className="text-[13px] leading-[1.4] text-stone sm:text-[15px] sm:leading-[1.45]">
                {next.where}
                {next.place && (
                  <>
                    <br />
                    {next.place}
                  </>
                )}
              </div>
            )}
            {next?.who && <div className="text-[13px] text-soft sm:text-sm">{next.who}</div>}
          </div>
        </div>
      )}
      {show !== "next" && (
        <div className="flex min-w-0 flex-col gap-3 rounded-3xl border border-line bg-linen p-5 sm:gap-3.5 sm:p-[26px]">
          <div className="flex flex-wrap items-baseline justify-between gap-2.5">
            <div className="text-[13px] font-bold uppercase tracking-[0.08em] text-subtle">Godziny w semestrze</div>
            <div className="flex gap-3.5 text-[13px] text-muted">
              <span>
                <strong className="font-heading text-[22px] text-ink">{fmtHours(hoursOnsite)}</strong> h stacjonarnie
              </span>
              <span>
                <strong className="font-heading text-[22px] text-ink">{fmtHours(hoursRemote)}</strong> h zdalnie
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-2.5">
            {shown.map((stat) => (
              <div key={stat.short} className="flex flex-col gap-[5px]">
                <div className="flex justify-between gap-2.5 text-sm">
                  <span className="font-bold">{stat.short}</span>
                  <span className="tabular text-muted">{fmtHours(stat.hours)} h</span>
                </div>
                <div className="h-[7px] overflow-hidden rounded-full bg-track">
                  <div className="h-full rounded-full" style={{ width: `${(stat.hours / max) * 100}%`, background: stat.color }} />
                </div>
              </div>
            ))}
            {stats.length === 0 && <div className="text-sm text-muted">Brak zajęć dla wybranych grup.</div>}
            {compact && stats.length > COMPACT_STATS && (
              <button
                type="button"
                onClick={() => setAllStats((value) => !value)}
                className="cursor-pointer self-start border-0 bg-transparent p-0 text-[13px] font-bold text-moss"
              >
                {allStats ? "Pokaż mniej" : `Pokaż wszystkie przedmioty (${stats.length})`}
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
