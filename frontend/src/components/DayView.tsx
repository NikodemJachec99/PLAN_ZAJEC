import { layoutLanes, sizeFor, type Item } from "../lib/model";
import { CancelledBadge, summary, titleStyle } from "./EventBits";

const HOUR = 80; // px per hour in the day view (design)

interface DayViewProps {
  items: Item[];
  range: { start: number; end: number };
  emptyHint: string;
}

export function DayView({ items, range, emptyHint }: DayViewProps) {
  const hours = Math.round((range.end - range.start) / 60);
  const labels = Array.from({ length: hours + 1 }, (_, index) => range.start / 60 + index);

  return (
    <div className="rounded-3xl border border-line bg-linen py-[18px] pl-2 pr-3.5">
      <div
        className="relative ml-14"
        style={{
          height: hours * HOUR,
          backgroundImage: `repeating-linear-gradient(to bottom,#e9e1cf 0 1px,transparent 1px ${HOUR}px)`,
        }}
      >
        {labels.map((hour, index) => (
          <div
            key={hour}
            className="tabular absolute -left-14 w-[46px] -translate-y-1/2 text-right text-xs font-bold text-faint"
            style={{ top: index * HOUR }}
          >
            {hour}:00
          </div>
        ))}

        {layoutLanes(items).map((item) => {
          const px = ((item.b - item.a) / 60) * HOUR;
          const size = sizeFor(px, 250);
          return (
            <div
              key={item.e.id}
              className="absolute pl-2"
              title={summary(item)}
              style={{
                left: `${(item.lane / item.lanes) * 100}%`,
                width: `${100 / item.lanes}%`,
                top: ((item.a - range.start) / 60) * HOUR,
                height: Math.max(22, px - 3),
                opacity: item.e.cancelled ? 0.6 : 1,
              }}
            >
              {size === "tiny" && (
                <div
                  className="flex h-full items-center gap-2.5 overflow-hidden whitespace-nowrap rounded-[10px] px-3"
                  style={{ background: item.pal.bg, borderLeft: `5px solid ${item.pal.dot}` }}
                >
                  <span className="tabular text-sm font-extrabold">{item.time}</span>
                  <span className="rounded-full px-2 py-0.5 text-[11px] font-extrabold text-linen" style={{ background: item.modeBg }}>
                    {item.modeShort}
                  </span>
                  <span className="overflow-hidden text-ellipsis text-sm font-extrabold" style={titleStyle(item)}>
                    {item.title}
                  </span>
                  <span className="min-w-0 flex-1 overflow-hidden text-ellipsis text-[13px] text-body2">
                    {item.type} · {item.where} · {item.who}
                  </span>
                </div>
              )}

              {size === "small" && (
                <div
                  className="flex h-full flex-col justify-center gap-1 overflow-hidden rounded-xl px-3.5 py-2"
                  style={{ background: item.pal.bg, borderLeft: `5px solid ${item.pal.dot}` }}
                >
                  <div className="flex items-center gap-2 overflow-hidden whitespace-nowrap">
                    <span className="tabular text-[15px] font-extrabold">{item.time}</span>
                    <span className="rounded-full px-2 py-0.5 text-[11px] font-extrabold text-linen" style={{ background: item.modeBg }}>
                      {item.modeShort}
                    </span>
                    <span className="text-xs font-extrabold" style={{ color: item.pal.c }}>
                      {item.type}
                    </span>
                    <CancelledBadge item={item} />
                  </div>
                  <div className="overflow-hidden text-ellipsis whitespace-nowrap text-[15px] font-extrabold" style={titleStyle(item)}>
                    {item.title}
                  </div>
                  <div className="overflow-hidden text-ellipsis whitespace-nowrap text-[13px] text-body2">
                    <strong className="text-ink">{item.where}</strong>
                    {item.who ? ` · ${item.who}` : ""} {item.note ? `· ${item.note}` : ""}
                  </div>
                </div>
              )}

              {size === "big" && (
                <div
                  className="flex h-full flex-col gap-2 overflow-hidden rounded-2xl px-4 py-3"
                  style={{ background: item.pal.bg, borderTop: `5px solid ${item.pal.dot}` }}
                >
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="tabular font-heading text-xl font-extrabold">{item.time}</span>
                    <span className="text-[13px] font-bold" style={{ color: item.pal.c }}>
                      {item.dur}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <span className="rounded-full px-2.5 py-1 text-xs font-extrabold text-linen" style={{ background: item.modeBg }}>
                      {item.modeLabel}
                    </span>
                    <span className="rounded-full bg-linen px-2.5 py-1 text-xs font-extrabold" style={{ color: item.pal.c }}>
                      {item.type}
                    </span>
                    <CancelledBadge item={item} />
                  </div>
                  <div className="text-pretty text-[17px] font-extrabold leading-tight" style={titleStyle(item)}>
                    {item.title}
                  </div>
                  <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-x-4 gap-y-2.5">
                    <div className="flex flex-col gap-0.5">
                      <div className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-subtle">Gdzie</div>
                      <div className="text-sm font-bold leading-[1.35]">{item.where}</div>
                      {item.place && <div className="text-[13px] leading-[1.4] text-body2">{item.place}</div>}
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <div className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-subtle">Z kim</div>
                      <div className="text-sm font-bold leading-[1.35]">{item.who || "—"}</div>
                      {item.note && <div className="text-[13px] leading-[1.4] text-body2">{item.note}</div>}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {items.length === 0 && (
          <div className="absolute left-2 right-0 top-32 flex flex-col items-center gap-2.5 rounded-[18px] border border-dashed border-rule bg-sand p-7 text-center">
            <div className="font-heading text-[22px] font-extrabold">Dzień wolny od zajęć</div>
            <div className="text-sm text-muted">{emptyHint}</div>
          </div>
        )}
      </div>
    </div>
  );
}
