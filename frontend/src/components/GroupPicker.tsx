import type { Dimension, Selection } from "../types";
import { groupCards, selectionLabel } from "../lib/model";

interface GroupPickerProps {
  dimensions: Dimension[];
  selection: Selection;
  onSelect: (dimensionId: string, value: string) => void;
  compact?: boolean;
  open?: boolean;
  onToggle?: () => void;
}

function pill(on: boolean): string {
  return on ? "bg-ink text-linen" : "bg-linen text-ink hover:bg-white";
}

const sectionLabel = "text-xs font-extrabold uppercase tracking-[0.06em] text-subtle max-sm:text-[11px]";

export function GroupPicker({ dimensions, selection, onSelect, compact = false, open = true, onToggle }: GroupPickerProps) {
  const group = dimensions.find((dim) => dim.id === "group");
  const others = dimensions.filter((dim) => dim.id !== "group");

  // Phones: once chosen, the groups shrink to one line so the plan is visible right away.
  if (compact && !open) {
    return (
      <section className="flex items-center justify-between gap-3 rounded-2xl border border-line bg-linen px-4 py-2.5">
        <div className="min-w-0">
          <div className="text-[11px] font-extrabold uppercase tracking-[0.06em] text-subtle">Twoje grupy</div>
          <div className="truncate font-heading text-lg font-extrabold leading-tight">{selectionLabel(selection, dimensions)}</div>
        </div>
        <button
          type="button"
          onClick={onToggle}
          className="h-9 flex-none cursor-pointer rounded-full border border-rule bg-linen px-4 text-[13px] font-bold text-ink"
        >
          Zmień
        </button>
      </section>
    );
  }

  return (
    <section className={`flex flex-col rounded-3xl border border-line bg-linen ${compact ? "gap-3 p-3" : "gap-[18px] p-5"}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className={`m-0 font-heading font-bold ${compact ? "text-lg" : "text-xl"}`}>Twoje grupy</h2>
        {compact ? (
          <button
            type="button"
            onClick={onToggle}
            className="h-8 cursor-pointer rounded-full border-0 bg-ink px-4 text-[13px] font-bold text-linen"
          >
            Gotowe
          </button>
        ) : (
          <div className="text-[13px] text-muted">Wybór zostaje zapamiętany na tym urządzeniu</div>
        )}
      </div>

      {group && (
        <div className="flex flex-col gap-2">
          <div className={sectionLabel}>{group.label}</div>
          <div className={compact ? "grid grid-cols-5 gap-1" : "grid grid-cols-[repeat(auto-fill,minmax(98px,1fr))] gap-2"}>
            {groupCards(group.options).map((card) => (
              <div key={card.num} className={`flex flex-col bg-sand ${compact ? "gap-1 rounded-xl p-1" : "gap-1.5 rounded-2xl p-2"}`}>
                <div className={`font-bold uppercase text-subtle ${compact ? "text-center text-[9px] tracking-[0.02em]" : "pl-1 text-[11px] tracking-[0.06em]"}`}>
                  {compact ? `Gr. ${card.num}` : `Grupa ${card.num}`}
                </div>
                <div className={`grid gap-1 ${card.subs.length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>
                  {card.subs.map((option) => (
                    <button
                      key={option}
                      type="button"
                      aria-pressed={selection.group === option}
                      onClick={() => onSelect("group", option)}
                      className={`cursor-pointer border-0 px-0 font-extrabold transition-colors ${compact ? "h-9 rounded-lg text-[13px]" : "h-11 rounded-[11px] text-base"} ${pill(selection.group === option)}`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {others.length > 0 && (
        <div className={`flex flex-wrap ${compact ? "gap-x-5 gap-y-3" : "gap-x-8 gap-y-4"}`}>
          {others.map((dim) => (
            <div key={dim.id} className="flex flex-col gap-2">
              <div className={sectionLabel}>{compact ? dim.label.split(" – ")[0] : dim.label}</div>
              <div className="flex flex-wrap gap-1 self-start rounded-[14px] bg-sand p-1">
                {dim.options.map((option) => (
                  <button
                    key={option}
                    type="button"
                    aria-pressed={selection[dim.id] === option}
                    onClick={() => onSelect(dim.id, option)}
                    className={`cursor-pointer rounded-[11px] border-0 font-extrabold transition-colors ${compact ? "h-9 min-w-11 px-2.5 text-sm" : "h-11 min-w-14 px-3 text-base"} ${pill(selection[dim.id] === option)}`}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {compact && <div className="text-xs text-muted">Wybór zostaje zapamiętany na tym urządzeniu.</div>}
    </section>
  );
}
