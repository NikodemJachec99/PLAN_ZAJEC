import { useEffect, useRef } from "react";

import { layoutLanes, MODE, sizeFor, type Item, type Placed } from "../lib/model";
import { hyphenate } from "../lib/hyphen";
import { clock } from "../lib/time";
import { summary, titleStyle } from "./EventBits";

const HOUR = 60; // px per hour in the week view (design)
const HOUR_COMPACT = 48; // phones: the whole week fits the screen width, so keep it short too

export interface WeekColumn {
  day: string;
  wd: string;
  num: number;
  isToday: boolean;
  items: Item[];
}

interface WeekViewProps {
  columns: WeekColumn[];
  range: { start: number; end: number };
  onOpenDay: (day: string) => void;
  compact?: boolean;
}

/** Phone card: time, then as many lines of the subject as fit, then the place. */
function CompactCard({ item, px }: { item: Placed; px: number }) {
  const showWhere = px >= 70;
  const lines = Math.max(1, Math.min(4, Math.floor((px - 16 - (showWhere ? 12 : 0)) / 12)));
  return (
    <>
      <span className="tabular w-full overflow-hidden whitespace-nowrap text-[9px] font-extrabold leading-[11px] tracking-[-0.02em]">
        {px >= 34 ? `${clock(item.e.start)}–${clock(item.e.end)}` : clock(item.e.start)}
      </span>
      <span
        className="w-full overflow-hidden text-[10.5px] font-extrabold leading-[12px] [overflow-wrap:anywhere]"
        style={{ ...titleStyle(item), display: "-webkit-box", WebkitLineClamp: lines, WebkitBoxOrient: "vertical" }}
      >
        {hyphenate(item.short)}
      </span>
      {showWhere && (
        <span className="w-full overflow-hidden text-ellipsis whitespace-nowrap text-[9px] font-bold leading-[11px] text-body2">
          {item.e.cancelled ? "ODWOŁANE" : item.whereShort}
        </span>
      )}
    </>
  );
}

export function WeekView({ columns, range, onOpenDay, compact = false }: WeekViewProps) {
  const hour = compact ? HOUR_COMPACT : HOUR;
  const hours = Math.round((range.end - range.start) / 60);
  const labels = Array.from({ length: hours + 1 }, (_, index) => range.start / 60 + index);
  const labelWidth = compact ? 30 : 52;
  const minWidth = compact ? undefined : labelWidth + columns.length * 142;
  const scroller = useRef<HTMLDivElement>(null);
  const todayIndex = columns.findIndex((column) => column.isToday);
  const weekKey = columns[0]?.day;

  // On phones only ~2 days fit: bring today's column into view.
  useEffect(() => {
    const element = scroller.current;
    if (!element || element.scrollWidth <= element.clientWidth) return;
    const columnWidth = (element.scrollWidth - labelWidth) / Math.max(columns.length, 1);
    element.scrollLeft = todayIndex > 0 ? todayIndex * columnWidth : 0;
  }, [weekKey, todayIndex, columns.length, labelWidth]);

  return (
    <>
      <div ref={scroller} className={`overflow-x-auto border border-line bg-linen ${compact ? "rounded-2xl" : "rounded-3xl"}`}>
        <div
          className={`grid ${compact ? "gap-x-[3px] pb-2 pl-0.5 pr-1.5 pt-1.5" : "gap-x-1.5 pb-4 pl-1 pr-3 pt-3"}`}
          style={{ minWidth, gridTemplateColumns: `${labelWidth}px repeat(${columns.length}, minmax(0, 1fr))` }}
        >
          <div />
          {columns.map((column) => (
            <button
              key={`head-${column.day}`}
              type="button"
              onClick={() => onOpenDay(column.day)}
              className={`flex cursor-pointer flex-col items-center gap-0.5 border-0 px-0.5 ${compact ? "mb-1.5 rounded-[10px] py-1" : "mb-2.5 rounded-[14px] px-1 py-2"} ${column.isToday ? "bg-clay text-linen" : "bg-transparent text-ink hover:bg-sand"}`}
            >
              <span className={`font-extrabold uppercase ${compact ? "text-[9px] tracking-[0.04em]" : "text-[11px] tracking-[0.08em]"}`}>{column.wd}</span>
              <span className={`font-heading font-extrabold leading-none ${compact ? "text-lg" : "text-2xl"}`}>{column.num}</span>
            </button>
          ))}

          <div className="relative" style={{ height: hours * hour }}>
            {labels.map((label, index) => (
              <div
                key={label}
                className={`tabular absolute -translate-y-1/2 font-bold text-faint ${compact ? "right-1 text-[9px]" : "right-1.5 text-[11px]"}`}
                style={{ top: index * hour }}
              >
                {label}:00
              </div>
            ))}
          </div>

          {columns.map((column) => (
            <div
              key={`col-${column.day}`}
              className={`relative ${compact ? "rounded-md" : "rounded-[10px]"}`}
              style={{
                height: hours * hour,
                backgroundColor: column.isToday ? "#fbf3e4" : "transparent",
                backgroundImage: `repeating-linear-gradient(to bottom,#e9e1cf 0 1px,transparent 1px ${hour}px)`,
              }}
            >
              {layoutLanes(column.items).map((item) => {
                const px = ((item.b - item.a) / 60) * hour;
                const narrow = item.lanes > 1;
                const size = sizeFor(px, narrow ? 150 : 120);
                const showWho = px >= (narrow ? 190 : 150);
                return (
                  <button
                    key={item.e.id}
                    type="button"
                    onClick={() => onOpenDay(column.day)}
                    title={summary(item)}
                    className={`absolute flex cursor-pointer flex-col overflow-hidden border-0 text-left text-ink ${compact ? "gap-px rounded-md py-0.5 pl-[3px] pr-px" : "gap-0.5 rounded-lg py-1 pl-[7px] pr-1.5"}`}
                    style={{
                      left: `${(item.lane / item.lanes) * 100}%`,
                      width: `${100 / item.lanes}%`,
                      top: ((item.a - range.start) / 60) * hour,
                      height: Math.max(compact ? 18 : 22, px - (compact ? 2 : 3)),
                      background: item.pal.bg,
                      borderLeft: `${compact ? 3 : 4}px solid ${item.pal.dot}`,
                      opacity: item.e.cancelled ? 0.6 : 1,
                    }}
                  >
                    {compact && <CompactCard item={item} px={px} />}
                    {!compact && size === "tiny" && (
                      <span className="flex w-full min-w-0 flex-col gap-px">
                        <span className="tabular flex items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap text-[10px] font-extrabold">
                          <span className="h-1.5 w-1.5 flex-none rounded-full" style={{ background: item.modeBg }} />
                          {item.time.split(" – ")[0]}
                        </span>
                        <span className="overflow-hidden text-ellipsis whitespace-nowrap text-[11px] font-extrabold leading-[1.15]" style={titleStyle(item)}>
                          {item.short}
                        </span>
                      </span>
                    )}
                    {!compact && size === "small" && (
                      <>
                        <span className="tabular flex items-center gap-1 whitespace-nowrap text-[11px] font-extrabold">
                          <span className="h-1.5 w-1.5 flex-none rounded-full" style={{ background: item.modeBg }} />
                          {item.time}
                        </span>
                        <span className="clamp-2 text-xs font-extrabold leading-[1.2]" style={titleStyle(item)}>
                          {item.short}
                        </span>
                        <span className="w-full overflow-hidden text-ellipsis whitespace-nowrap text-[11px] font-bold leading-[1.2] text-body2">
                          {item.typeShort} · {item.whereShort}
                        </span>
                      </>
                    )}
                    {!compact && size === "big" && (
                      <>
                        <span className="tabular flex items-center gap-[5px] whitespace-nowrap text-[11px] font-extrabold">
                          <span className="h-[7px] w-[7px] flex-none rounded-full" style={{ background: item.modeBg }} />
                          {item.time}
                        </span>
                        <span className="text-[13px] font-extrabold leading-[1.2]" style={titleStyle(item)}>
                          {item.short}
                        </span>
                        <span className="text-[11px] font-bold leading-[1.25] text-body2">
                          {item.e.cancelled ? "ODWOŁANE · " : ""}
                          {item.typeShort} · {item.whereShort}
                        </span>
                        {showWho && <span className="text-[11px] leading-[1.25] text-muted">{item.who}</span>}
                      </>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 px-1 text-[11px] font-semibold sm:gap-y-2 sm:text-[13px]">
        <div className="flex items-center gap-[7px]">
          <span className="h-[9px] w-[9px] rounded-full" style={{ background: MODE.onsite.color }} />
          stacjonarnie
        </div>
        <div className="flex items-center gap-[7px]">
          <span className="h-[9px] w-[9px] rounded-full" style={{ background: MODE.remote.color }} />
          zdalnie (MS Teams)
        </div>
        <div className="flex items-center gap-[7px]">
          <span className="h-[9px] w-[9px] rounded-full" style={{ background: MODE.unassigned.color }} />
          sala nieprzypisana
        </div>
      </div>
    </>
  );
}
