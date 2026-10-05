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
    <section className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap gap-0.5 rounded-3xl bg-stone p-1" role="tablist" aria-label="Widok planu">
        {VIEWS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={view === id}
            onClick={() => onView(id)}
            className={`h-11 cursor-pointer whitespace-nowrap rounded-full border-0 px-[18px] text-[15px] font-bold text-ink ${view === id ? "bg-linen" : "bg-transparent hover:bg-white/40"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {view === "lista" && (
          <button
            type="button"
            onClick={onTogglePast}
            className="flex h-11 cursor-pointer items-center gap-2 whitespace-nowrap rounded-full border border-rule bg-linen px-4 text-sm font-bold text-ink"
          >
            <span className="h-4 w-4 rounded-[5px] border-2 border-ink" style={{ background: showPast ? "#12110f" : "transparent" }} />
            Pokaż minione
          </button>
        )}
        <button
          type="button"
          onClick={onSubscribe}
          title="Skopiuj link do kalendarza, który sam się aktualizuje (Google, Apple, Outlook)"
          className="h-11 cursor-pointer whitespace-nowrap rounded-full border border-rule bg-linen px-4 text-sm font-bold text-ink hover:bg-white"
        >
          Subskrybuj
        </button>
        <a
          href={icsHref}
          className="flex h-11 items-center whitespace-nowrap rounded-full bg-moss px-[18px] text-sm font-bold text-linen no-underline hover:bg-moss-dark hover:text-linen"
        >
          Dodaj do kalendarza (.ics)
        </a>
      </div>
    </section>
  );
}
