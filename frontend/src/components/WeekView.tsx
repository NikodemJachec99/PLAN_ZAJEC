import { useEffect, useRef } from "react";

import { layoutLanes, MODE, sizeFor, type Item } from "../lib/model";
import { summary, titleStyle } from "./EventBits";

const HOUR = 60; // px per hour in the week view (design)

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
}

export function WeekView({ columns, range, onOpenDay }: WeekViewProps) {
  const hours = Math.round((range.end - range.start) / 60);
  const labels = Array.from({ length: hours + 1 }, (_, index) => range.start / 60 + index);
  const minWidth = 52 + columns.length * 142;
  const scroller = useRef<HTMLDivElement>(null);
  const todayIndex = columns.findIndex((column) => column.isToday);
  const weekKey = columns[0]?.day;

  // On phones only ~2 days fit: bring today's column into view.
  useEffect(() => {
    const element = scroller.current;
    if (!element || element.scrollWidth <= element.clientWidth) return;
    const columnWidth = (element.scrollWidth - 52) / Math.max(columns.length, 1);
    element.scrollLeft = todayIndex > 0 ? todayIndex * columnWidth : 0;
  }, [weekKey, todayIndex, columns.length]);

  return (
    <>
      <div ref={scroller} className="overflow-x-auto rounded-3xl border border-line bg-linen">
        <div
          className="grid gap-x-1.5 pb-4 pl-1 pr-3 pt-3"
          style={{ minWidth, gridTemplateColumns: `52px repeat(${columns.length}, minmax(0, 1fr))` }}
        >
          <div />
          {columns.map((column) => (
            <button
              key={`head-${column.day}`}
              type="button"
              onClick={() => onOpenDay(column.day)}
              className={`mb-2.5 flex cursor-pointer flex-col items-center gap-0.5 rounded-[14px] border-0 px-1 py-2 ${column.isToday ? "bg-clay text-linen" : "bg-transparent text-ink hover:bg-sand"}`}
            >
              <span className="text-[11px] font-extrabold uppercase tracking-[0.08em]">{column.wd}</span>
              <span className="font-heading text-2xl font-extrabold leading-none">{column.num}</span>
            </button>
          ))}

          <div className="relative" style={{ height: hours * HOUR }}>
            {labels.map((hour, index) => (
              <div
                key={hour}
                className="tabular absolute right-1.5 -translate-y-1/2 text-[11px] font-bold text-faint"
                style={{ top: index * HOUR }}
              >
                {hour}:00
              </div>
            ))}
          </div>

          {columns.map((column) => (
            <div
              key={`col-${column.day}`}
              className="relative rounded-[10px]"
              style={{
                height: hours * HOUR,
                backgroundColor: column.isToday ? "#fbf3e4" : "transparent",
                backgroundImage: `repeating-linear-gradient(to bottom,#e9e1cf 0 1px,transparent 1px ${HOUR}px)`,
              }}
            >
              {layoutLanes(column.items).map((item) => {
                const px = ((item.b - item.a) / 60) * HOUR;
                const narrow = item.lanes > 1;
                const size = sizeFor(px, narrow ? 150 : 120);
                const showWho = px >= (narrow ? 190 : 150);
                return (
                  <button
                    key={item.e.id}
                    type="button"
                    onClick={() => onOpenDay(column.day)}
                    title={summary(item)}
                    className="absolute flex cursor-pointer flex-col gap-0.5 overflow-hidden rounded-lg border-0 py-1 pl-[7px] pr-1.5 text-left text-ink"
                    style={{
                      left: `${(item.lane / item.lanes) * 100}%`,
                      width: `${100 / item.lanes}%`,
                      top: ((item.a - range.start) / 60) * HOUR,
                      height: Math.max(22, px - 3),
                      background: item.pal.bg,
                      borderLeft: `4px solid ${item.pal.dot}`,
                      opacity: item.e.cancelled ? 0.6 : 1,
                    }}
                  >
                    {size === "tiny" && (
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
                    {size === "small" && (
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
                    {size === "big" && (
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
      <div className="flex flex-wrap gap-x-4 gap-y-2 px-1 text-[13px] font-semibold">
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
