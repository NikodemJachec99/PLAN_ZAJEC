import type { Dimension, Selection } from "../types";
import { groupCards } from "../lib/model";

interface GroupPickerProps {
  dimensions: Dimension[];
  selection: Selection;
  onSelect: (dimensionId: string, value: string) => void;
}

function pill(on: boolean): string {
  return on ? "bg-ink text-linen" : "bg-linen text-ink hover:bg-white";
}

const sectionLabel = "text-xs font-extrabold uppercase tracking-[0.06em] text-subtle";

export function GroupPicker({ dimensions, selection, onSelect }: GroupPickerProps) {
  const group = dimensions.find((dim) => dim.id === "group");
  const others = dimensions.filter((dim) => dim.id !== "group");

  return (
    <section className="flex flex-col gap-[18px] rounded-3xl border border-line bg-linen p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 font-heading text-xl font-bold">Twoje grupy</h2>
        <div className="text-[13px] text-muted">Wybór zostaje zapamiętany na tym urządzeniu</div>
      </div>

      {group && (
        <div className="flex flex-col gap-2">
          <div className={sectionLabel}>{group.label}</div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(98px,1fr))] gap-2">
            {groupCards(group.options).map((card) => (
              <div key={card.num} className="flex flex-col gap-1.5 rounded-2xl bg-sand p-2">
                <div className="pl-1 text-[11px] font-bold uppercase tracking-[0.06em] text-subtle">Grupa {card.num}</div>
                <div className={`grid gap-1 ${card.subs.length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>
                  {card.subs.map((option) => (
                    <button
                      key={option}
                      type="button"
                      aria-pressed={selection.group === option}
                      onClick={() => onSelect("group", option)}
                      className={`h-11 cursor-pointer rounded-[11px] border-0 text-base font-extrabold transition-colors ${pill(selection.group === option)}`}
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
        <div className="flex flex-wrap gap-x-8 gap-y-4">
          {others.map((dim) => (
            <div key={dim.id} className="flex flex-col gap-2">
              <div className={sectionLabel}>{dim.label}</div>
              <div className="flex flex-wrap gap-1 self-start rounded-[14px] bg-sand p-1">
                {dim.options.map((option) => (
                  <button
                    key={option}
                    type="button"
                    aria-pressed={selection[dim.id] === option}
                    onClick={() => onSelect(dim.id, option)}
                    className={`h-11 min-w-14 cursor-pointer rounded-[11px] border-0 px-3 text-base font-extrabold transition-colors ${pill(selection[dim.id] === option)}`}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
