import type { Plan, SourceInfo, Status } from "../types";
import { localClock, shortDate, timeAgo } from "../lib/time";

interface HeaderProps {
  plan?: Plan;
  sources: SourceInfo[];
  status?: Status;
  checking: boolean;
  onCheck: () => void;
}

const KIND_DOT: Record<string, string> = { main: "#355f48", practical: "#cc5c2d" };

function eyebrow(plan?: Plan): string {
  const year = plan?.meta.year ? `${plan.meta.year} rok` : "";
  const level = plan?.meta.level ? `Pielęgniarstwo ${plan.meta.level} stopnia` : "Pielęgniarstwo";
  return [year, level, "stacjonarne"].filter(Boolean).join(" · ");
}

function subtitle(plan?: Plan): string {
  const semester = plan?.meta.semester ? `Semestr ${plan.meta.semester}` : "";
  const term = [semester, plan?.meta.academic_year].filter(Boolean).join(" ");
  return [term, "wykłady, ćwiczenia, lektorat i zajęcia praktyczne w jednym miejscu"].filter(Boolean).join(" · ");
}

export function Header({ plan, sources, status, checking, onCheck }: HeaderProps) {
  const sync = status?.sync;
  const healthy = sync?.healthy ?? true;
  const checkedLabel =
    checking || sync?.running
      ? "sprawdzam stronę uczelni…"
      : sync?.last_checked_at
        ? `sprawdzono ${timeAgo(sync.last_checked_at, status?.now)}`
        : "czekam na pierwsze sprawdzenie";

  return (
    <header className="flex flex-wrap items-end justify-between gap-5">
      <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-2.5">
        <div className="text-[13px] font-bold uppercase tracking-[0.08em] text-moss">{eyebrow(plan)}</div>
        <h1 className="text-balance m-0 font-heading text-[clamp(36px,5.6vw,64px)] font-extrabold leading-[0.98] tracking-[-0.025em]">
          Plan zajęć
        </h1>
        <div className="text-base text-muted">{subtitle(plan)}</div>
      </div>
      <div className="flex flex-none flex-col items-end gap-1.5 max-sm:w-full max-sm:items-start">
        {sources.map((source) => (
          <a
            key={source.id}
            href={source.url || undefined}
            target="_blank"
            rel="noreferrer"
            title={source.name}
            className="flex items-center gap-2 whitespace-nowrap rounded-full border border-line bg-linen px-3 py-[7px] text-[13px] font-bold text-ink no-underline hover:text-ink"
          >
            <span className="h-2 w-2 rounded-full" style={{ background: KIND_DOT[source.kind] ?? "#8a8373" }} />
            {source.label}
            {source.as_of ? ` · stan na ${shortDate(source.as_of)}` : ""}
            {source.stale ? " · poprzednia wersja" : ""}
          </a>
        ))}
        <button
          type="button"
          onClick={onCheck}
          title={
            sync
              ? `Plan jest pobierany automatycznie co ${Math.round(sync.interval_seconds / 60)} min ze strony uczelni.\nOstatnia zmiana planu: ${localClock(sync.last_changed_at) || "—"}\nKliknij, aby sprawdzić teraz.`
              : "Kliknij, aby sprawdzić teraz."
          }
          className="flex cursor-pointer items-center gap-2 whitespace-nowrap rounded-full border-0 bg-transparent px-1 py-0.5 text-xs font-semibold text-subtle hover:text-ink"
        >
          <span
            className={`h-2 w-2 rounded-full ${checking || sync?.running ? "animate-pulse" : ""}`}
            style={{ background: healthy ? "#355f48" : "#cc5c2d" }}
          />
          Aktualizuje się automatycznie · {checkedLabel}
        </button>
      </div>
    </header>
  );
}
