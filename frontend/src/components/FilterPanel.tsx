import { Filter, RotateCcw, SlidersHorizontal, X } from "lucide-react";
import { useMemo, useState } from "react";

import { cn } from "../lib/cn";
import type { ActiveFilters, FilterCategory, FilterOptions } from "../types";

interface FilterPanelProps {
  options?: FilterOptions;
  filters: ActiveFilters;
  onToggleValue: (category: FilterCategory, value: string) => void;
  onClearCategory: (category: FilterCategory) => void;
  onToggleOnlyMagdalenka: () => void;
  onClearAll: () => void;
}

const LABELS: Record<FilterCategory, string> = {
  subject: "Przedmiot",
  instructor: "Prowadzacy",
  room: "Sala",
  group: "Grupa",
  oddzial: "Oddzial",
  type: "Typ zajec",
};

function FilterGroup({
  category,
  values,
  selected,
  onToggle,
  onClear,
}: {
  category: FilterCategory;
  values: string[];
  selected: string[];
  onToggle: (category: FilterCategory, value: string) => void;
  onClear: (category: FilterCategory) => void;
}) {
  const count = selected.length;

  return (
    <div className="rounded-2xl border border-black/10 bg-white/80 p-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm font-semibold text-ink">{LABELS[category]}</p>
        <button
          type="button"
          className="text-xs font-semibold text-clay disabled:text-black/30"
          disabled={count === 0}
          onClick={() => onClear(category)}
        >
          Wyczysc
        </button>
      </div>
      <p className="mb-2 text-xs text-black/60">Wybrane: {count}</p>

      <div className="max-h-36 space-y-1 overflow-y-auto pr-1">
        {values.length === 0 ? (
          <p className="text-xs text-black/40">Brak wartosci</p>
        ) : (
          values.map((value) => {
            const checked = selected.includes(value);
            return (
              <label
                key={`${category}-${value}`}
                className={cn(
                  "flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 text-sm",
                  checked ? "bg-moss/10 text-ink" : "text-black/70 hover:bg-black/5",
                )}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => onToggle(category, value)}
                  className="h-4 w-4 accent-moss"
                />
                <span className="truncate">{value}</span>
              </label>
            );
          })
        )}
      </div>
    </div>
  );
}

function FilterPanelContent({
  options,
  filters,
  onToggleValue,
  onClearCategory,
  onToggleOnlyMagdalenka,
  onClearAll,
}: FilterPanelProps) {
  const categories = useMemo(() => (Object.keys(LABELS) as FilterCategory[]), []);

  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-black/10 bg-white p-4 shadow-panel">
        <div className="mb-3 flex items-center justify-between">
          <p className="font-heading text-lg font-bold text-ink">Filtry</p>
          <button
            type="button"
            onClick={onClearAll}
            className="inline-flex items-center gap-2 rounded-lg border border-black/15 px-2 py-1 text-xs font-semibold text-black/70 hover:bg-black/5"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Reset
          </button>
        </div>

        <button
          type="button"
          onClick={onToggleOnlyMagdalenka}
          className={cn(
            "mb-4 inline-flex w-full items-center justify-between rounded-xl border px-3 py-2 text-sm font-semibold",
            filters.only_magdalenka
              ? "border-clay bg-clay/10 text-clay"
              : "border-black/10 bg-sand text-black/70 hover:bg-sand/70",
          )}
        >
          <span>Tylko grupy Magdalenki</span>
          <span
            className={cn(
              "inline-block h-2.5 w-2.5 rounded-full",
              filters.only_magdalenka ? "bg-clay" : "bg-black/20",
            )}
          />
        </button>

        <div className="space-y-3">
          {categories.map((category) => (
            <FilterGroup
              key={category}
              category={category}
              values={options?.[category] ?? []}
              selected={filters[category]}
              onToggle={onToggleValue}
              onClear={onClearCategory}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export function FilterPanel(props: FilterPanelProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      <div className="lg:hidden">
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          className="inline-flex items-center gap-2 rounded-xl border border-black/15 bg-white px-4 py-2 text-sm font-semibold text-ink shadow-panel"
        >
          <SlidersHorizontal className="h-4 w-4" /> Filtry
        </button>
      </div>

      <aside className="hidden lg:block lg:sticky lg:top-4 lg:h-fit">
        <FilterPanelContent {...props} />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 bg-black/45 p-3 lg:hidden">
          <div className="mx-auto h-full max-w-md overflow-hidden rounded-2xl bg-linen shadow-panel">
            <div className="flex items-center justify-between border-b border-black/10 px-4 py-3">
              <p className="inline-flex items-center gap-2 font-heading text-lg font-bold text-ink">
                <Filter className="h-4 w-4" /> Filtry
              </p>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="rounded-lg p-1 text-black/70 hover:bg-black/5"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="h-[calc(100%-58px)] overflow-y-auto p-3">
              <FilterPanelContent {...props} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
