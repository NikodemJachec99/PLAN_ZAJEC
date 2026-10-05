interface NavigatorProps {
  label: string;
  sub: string;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
  onNextClass: () => void;
}

const arrow =
  "h-12 w-12 flex-none cursor-pointer rounded-full border border-rule bg-linen text-[22px] font-bold text-ink transition-colors hover:bg-ink hover:text-linen";
const chip = "h-9 cursor-pointer rounded-full border border-rule bg-linen px-3.5 text-[13px] font-bold text-ink hover:bg-white";

export function Navigator({ label, sub, onPrev, onNext, onToday, onNextClass }: NavigatorProps) {
  return (
    <>
      <div className="flex items-center gap-2.5">
        <button type="button" onClick={onPrev} aria-label="Wstecz" className={arrow}>
          ‹
        </button>
        <div className="flex min-w-0 flex-1 flex-col items-center gap-0.5 text-center">
          <div className="font-heading text-[clamp(20px,3vw,28px)] font-extrabold leading-[1.1] tracking-[-0.01em]">{label}</div>
          <div className="text-[13px] font-semibold text-subtle">{sub}</div>
        </div>
        <button type="button" onClick={onNext} aria-label="Dalej" className={arrow}>
          ›
        </button>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        <button type="button" onClick={onToday} className={chip}>
          Dziś
        </button>
        <button type="button" onClick={onNextClass} className={chip}>
          Najbliższe zajęcia
        </button>
        <div className="flex h-9 items-center text-xs text-subtle max-sm:hidden">Strzałki ← → na klawiaturze</div>
      </div>
    </>
  );
}
