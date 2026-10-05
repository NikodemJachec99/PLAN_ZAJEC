import type { Item } from "../lib/model";

export function CancelledBadge({ item }: { item: Item }) {
  if (!item.e.cancelled) return null;
  return <span className="rounded-full bg-clay px-2 py-0.5 text-[11px] font-extrabold text-linen">Odwołane</span>;
}

export function titleStyle(item: Item): React.CSSProperties {
  return { color: item.pal.c, textDecoration: item.e.cancelled ? "line-through" : undefined };
}

/** Plain-text summary used for tooltips and screen readers. */
export function summary(item: Item): string {
  return [
    `${item.time} · ${item.title}`,
    `${item.type} · ${item.modeLabel}`,
    [item.where, item.place].filter(Boolean).join(", "),
    item.who,
    item.note,
    item.e.cancelled ? "ODWOŁANE" : "",
  ]
    .filter(Boolean)
    .join("\n");
}
