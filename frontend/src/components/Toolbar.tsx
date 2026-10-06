import type { View } from "../types";

interface ToolbarProps {
  view: View;
  onView: (view: View) => void;
  showPast: boolean;
  onTogglePast: () => void;
  icsHref: string;
  onSubscribe: () => void;
}

const VIEWS: [View, string][] = [
  ["dzień", "Dzień"],
  ["tydzień", "Tydzień"],
  ["kalendarz", "Miesiąc"],
  ["lista", "Lista"],
];

export function Toolbar({ view, onView, showPast, onTogglePast, icsHref, onSubscribe }: ToolbarProps) {
  return (
    <section className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
      <div className="flex flex-wrap gap-0.5 rounded-3xl bg-stone p-1 max-sm:grid max-sm:w-full max-sm:grid-cols-4" role="tablist" aria-label="Widok planu">
        {VIEWS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={view === id}
            onClick={() => onView(id)}
            className={`h-11 cursor-pointer whitespace-nowrap rounded-full border-0 px-[18px] text-[15px] font-bold text-ink max-sm:h-9 max-sm:px-1 max-sm:text-[13px] ${view === id ? "bg-linen" : "bg-transparent hover:bg-white/40"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2 max-sm:w-full max-sm:flex-nowrap">
        {view === "lista" && (
          <button
            type="button"
            onClick={onTogglePast}
            className="flex h-11 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-full border border-rule bg-linen px-4 text-sm font-bold text-ink max-sm:h-9 max-sm:flex-1 max-sm:gap-1.5 max-sm:px-2 max-sm:text-xs"
          >
            <span className="h-4 w-4 flex-none rounded-[5px] border-2 border-ink max-sm:h-3.5 max-sm:w-3.5" style={{ background: showPast ? "#12110f" : "transparent" }} />
            <span className="max-sm:hidden">Pokaż minione</span>
            <span className="sm:hidden">Minione</span>
          </button>
        )}
        <button
          type="button"
          onClick={onSubscribe}
          title="Skopiuj link do kalendarza, który sam się aktualizuje (Google, Apple, Outlook)"
          className="h-11 cursor-pointer whitespace-nowrap rounded-full border border-rule bg-linen px-4 text-sm font-bold text-ink hover:bg-white max-sm:h-9 max-sm:min-w-0 max-sm:flex-1 max-sm:px-2 max-sm:text-xs"
        >
          Subskrybuj
        </button>
        <a
          href={icsHref}
          className="flex h-11 items-center justify-center whitespace-nowrap rounded-full bg-moss px-[18px] text-sm font-bold text-linen no-underline hover:bg-moss-dark hover:text-linen max-sm:h-9 max-sm:min-w-0 max-sm:flex-1 max-sm:px-2 max-sm:text-xs"
        >
          <span className="max-sm:hidden">Dodaj do kalendarza (.ics)</span>
          <span className="sm:hidden">Pobierz .ics</span>
        </a>
      </div>
    </section>
  );
}
