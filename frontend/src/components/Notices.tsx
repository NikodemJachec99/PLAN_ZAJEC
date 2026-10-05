import type { SourceInfo, Status } from "../types";
import { localClock, timeAgo } from "../lib/time";

interface NoticesProps {
  sources: SourceInfo[];
  status?: Status;
}

/** Shown only when something needs attention: the faculty site can't be read or a file is outdated. */
export function Notices({ sources, status }: NoticesProps) {
  const messages: string[] = [];
  const sync = status?.sync;
  if (sync && !sync.healthy && sync.last_checked_at) {
    messages.push(
      sync.last_success_at
        ? `Nie udaje się teraz sprawdzić strony uczelni (ostatnio udało się ${timeAgo(sync.last_success_at, status?.now)}) – wyświetlamy ostatnią pobraną wersję planu.`
        : "Nie udało się jeszcze pobrać planu ze strony uczelni – wyświetlamy wersję zapisaną na serwerze.",
    );
  }
  sources
    .filter((source) => source.stale)
    .forEach((source) => messages.push(`${source.label}: ${source.warnings[source.warnings.length - 1] ?? "pokazujemy poprzednią wersję pliku."}`));

  if (messages.length === 0) return null;
  return (
    <div className="rounded-2xl border border-[#e8c9a8] bg-[#fbeee0] px-4 py-3 text-sm leading-relaxed text-[#6b3a17]" role="status">
      {messages.map((message) => (
        <div key={message}>{message}</div>
      ))}
      {sync?.last_error && (
        <div className="mt-1 text-xs opacity-80">
          Szczegóły: {sync.last_error} {sync.last_error_at ? `(${localClock(sync.last_error_at)})` : ""}
        </div>
      )}
    </div>
  );
}

interface ToastProps {
  message: string | null;
  onClose: () => void;
}

export function Toast({ message, onClose }: ToastProps) {
  if (!message) return null;
  return (
    <div className="toast-in fixed bottom-5 left-1/2 z-50 flex w-[min(92vw,520px)] -translate-x-1/2 items-start gap-3 rounded-2xl bg-ink px-4 py-3 text-sm text-linen shadow-[0_18px_40px_-18px_rgba(0,0,0,0.6)]">
      <span className="mt-1 h-2.5 w-2.5 flex-none rounded-full bg-clay" />
      <span className="flex-1 leading-snug">{message}</span>
      <button type="button" onClick={onClose} aria-label="Zamknij" className="cursor-pointer border-0 bg-transparent text-lg leading-none text-soft hover:text-linen">
        ×
      </button>
    </div>
  );
}
