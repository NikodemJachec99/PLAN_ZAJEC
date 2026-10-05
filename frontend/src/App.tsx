import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { DayView } from "./components/DayView";
import { GroupPicker } from "./components/GroupPicker";
import { Header } from "./components/Header";
import { ListView } from "./components/ListView";
import { MonthView } from "./components/MonthView";
import { Navigator } from "./components/Navigator";
import { Notices, Toast } from "./components/Notices";
import { Overview, type Stat } from "./components/Overview";
import { Toolbar } from "./components/Toolbar";
import { WeekView, type WeekColumn } from "./components/WeekView";
import { calendarUrl, fetchPlan, fetchStatus, requestSync } from "./lib/api";
import { decorate, hourRange, loadSelection, matches, saveSelection, selectionLabel, type Item } from "./lib/model";
import { readJson, writeStorage } from "./lib/storage";
import {
  clock,
  dayLong,
  fmtHours,
  isoDay,
  isWeekend,
  MONG,
  mondayOf,
  nowInWarsaw,
  parseDay,
  plural,
  shift,
  shortDate,
  WD,
  WDL,
} from "./lib/time";
import type { Plan, Selection, View } from "./types";

const PLAN_CACHE_KEY = "planzp-plan-cache-v2";
const STATUS_POLL_MS = 60_000;

function useNow() {
  const [now, setNow] = useState(nowInWarsaw);
  useEffect(() => {
    const id = window.setInterval(() => setNow(nowInWarsaw()), 30_000);
    return () => window.clearInterval(id);
  }, []);
  return now;
}

export default function App() {
  const now = useNow();
  const today = now.today;
  const cachedPlan = useMemo(() => readJson<Plan>(PLAN_CACHE_KEY), []);

  const planQuery = useQuery({
    queryKey: ["plan"],
    queryFn: fetchPlan,
    initialData: cachedPlan ?? undefined,
    initialDataUpdatedAt: 0,
    refetchOnWindowFocus: false,
  });
  const statusQuery = useQuery({
    queryKey: ["status"],
    queryFn: fetchStatus,
    refetchInterval: STATUS_POLL_MS,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
  });

  const plan = planQuery.data;
  const status = statusQuery.data;
  // Status is polled every minute, so its file descriptions are the freshest.
  const sources = status?.sources.length ? status.sources : (plan?.sources ?? []);
  const { refetch: refetchPlan } = planQuery;

  // The server re-checks the faculty page every few minutes; whenever it reports a new
  // version, pull the new plan right away.
  useEffect(() => {
    if (status?.version && plan?.version && status.version !== plan.version) {
      void refetchPlan();
    }
  }, [status?.version, plan?.version, refetchPlan]);

  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number>();
  const showToast = useCallback((message: string, ms = 8000) => {
    setToast(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), ms);
  }, []);

  const shownVersion = useRef<string | undefined>(cachedPlan?.version);
  useEffect(() => {
    if (!plan || plan.version === shownVersion.current) return;
    const hadPrevious = shownVersion.current !== undefined;
    shownVersion.current = plan.version;
    writeStorage(PLAN_CACHE_KEY, JSON.stringify(plan));
    if (hadPrevious) {
      const details = plan.sources
        .map((source) => `${source.label.toLowerCase()}${source.as_of ? ` (stan na ${shortDate(source.as_of)})` : ""}`)
        .join(", ");
      showToast(`Plan został zaktualizowany ze strony uczelni: ${details}.`, 12_000);
    }
  }, [plan, showToast]);

  // ------------------------------------------------------------------ groups (remembered per device)

  const [selection, setSelection] = useState<Selection>(() => (cachedPlan ? loadSelection(cachedPlan.dimensions) : {}));
  const dimensions = useMemo(() => plan?.dimensions ?? [], [plan?.dimensions]);
  useEffect(() => {
    if (!dimensions.length) return;
    setSelection(loadSelection(dimensions));
  }, [dimensions]);

  const selectOption = (dimensionId: string, value: string) => {
    saveSelection(dimensionId, value);
    setSelection((previous) => ({ ...previous, [dimensionId]: value }));
  };

  // ------------------------------------------------------------------ derived data

  const subjects = useMemo(() => new Map((plan?.subjects ?? []).map((subject) => [subject.key, subject])), [plan?.subjects]);
  const items = useMemo<Item[]>(
    () => (plan?.events ?? []).filter((event) => matches(event, selection)).map((event) => decorate(event, subjects)),
    [plan?.events, selection, subjects],
  );
  const byDay = useMemo(() => {
    const map = new Map<string, Item[]>();
    items.forEach((item) => map.set(item.e.date, [...(map.get(item.e.date) ?? []), item]));
    return map;
  }, [items]);
  const range = useMemo(() => hourRange(plan), [plan]);
  const showWeekends = useMemo(() => items.some((item) => isWeekend(parseDay(item.e.date))), [items]);

  const upcoming = items.filter((item) => !item.e.cancelled && (item.e.date > today || (item.e.date === today && item.b > now.minutes)));
  const next = upcoming[0];
  const nextLive = Boolean(next && next.e.date === today && next.a <= now.minutes);

  const { stats, hoursOnsite, hoursRemote } = useMemo(() => {
    const totals = new Map<string, Stat>();
    let onsite = 0;
    let remote = 0;
    items.forEach((item) => {
      if (item.e.cancelled) return;
      const stat = totals.get(item.short) ?? { short: item.short, color: item.pal.dot, hours: 0 };
      stat.hours += item.hours;
      totals.set(item.short, stat);
      if (item.e.mode === "remote") remote += item.hours;
      else onsite += item.hours;
    });
    return {
      stats: [...totals.values()].sort((x, y) => y.hours - x.hours),
      hoursOnsite: onsite,
      hoursRemote: remote,
    };
  }, [items]);

  const months = useMemo(() => [...new Set([...byDay.keys()].map((day) => day.slice(0, 7)))].sort(), [byDay]);

  // ------------------------------------------------------------------ navigation

  const [view, setView] = useState<View>("tydzień");
  const [cursor, setCursor] = useState<string | null>(null);
  const [showPast, setShowPast] = useState(false);
  const current = cursor ?? next?.e.date ?? today;
  const cursorDate = parseDay(current);
  const isDay = view === "dzień";
  const isWeek = view === "tydzień";

  const stepDay = useCallback(
    (direction: number) => {
      let day = shift(parseDay(current), direction);
      for (let guard = 0; guard < 7 && isWeekend(day) && !byDay.has(isoDay(day)); guard += 1) {
        day = shift(day, direction);
      }
      setCursor(isoDay(day));
    },
    [current, byDay],
  );
  const navigate = useCallback(
    (direction: number) => {
      if (view === "dzień") stepDay(direction);
      else if (view === "tydzień") setCursor(isoDay(shift(parseDay(current), 7 * direction)));
    },
    [view, stepDay, current],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && /input|textarea|select/i.test(target.tagName)) return;
      if (event.key === "ArrowLeft") navigate(-1);
      if (event.key === "ArrowRight") navigate(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);

  const openDay = (day: string) => {
    setView("dzień");
    setCursor(day);
  };

  const monday = mondayOf(cursorDate);
  const friday = shift(monday, 4);
  const weekColumns: WeekColumn[] = Array.from({ length: 7 }, (_, index) => shift(monday, index))
    .filter((day) => !isWeekend(day) || byDay.has(isoDay(day)))
    .map((day) => {
      const key = isoDay(day);
      return { day: key, wd: WD[day.getDay()], num: day.getDate(), isToday: key === today, items: byDay.get(key) ?? [] };
    });
  const weekDaysWithClasses = weekColumns.filter((column) => column.items.length).length;
  const dayItems = byDay.get(current) ?? [];
  const dayHours = dayItems.reduce((sum, item) => sum + item.hours, 0);
  const nextAfter = items.find((item) => item.e.date > current && !item.e.cancelled);

  const navLabel = isDay
    ? dayLong(current)
    : monday.getMonth() === friday.getMonth()
      ? `${monday.getDate()} – ${friday.getDate()} ${MONG[friday.getMonth()]}`
      : `${monday.getDate()} ${MONG[monday.getMonth()]} – ${friday.getDate()} ${MONG[friday.getMonth()]}`;
  const navSub = isDay
    ? `${cursorDate.getFullYear()} · ${
        dayItems.length
          ? `${dayItems.length} ${plural(dayItems.length, "blok", "bloki", "bloków")} · ${fmtHours(dayHours)} h`
          : "brak zajęć"
      }`
    : `${friday.getFullYear()} · ${weekDaysWithClasses} ${plural(weekDaysWithClasses, "dzień", "dni", "dni")} z zajęciami`;
  const emptyHint = nextAfter
    ? `Kolejne zajęcia: ${WDL[parseDay(nextAfter.e.date).getDay()]}, ${parseDay(nextAfter.e.date).getDate()} ${MONG[parseDay(nextAfter.e.date).getMonth()]}, ${clock(nextAfter.e.start)}`
    : "To już koniec zajęć w tym semestrze.";

  // ------------------------------------------------------------------ actions

  const [checking, setChecking] = useState(false);
  const checkNow = async () => {
    setChecking(true);
    try {
      const accepted = await requestSync();
      showToast(accepted ? "Sprawdzam stronę uczelni… Jeśli pojawiły się nowe pliki, plan odświeży się sam." : "Strona uczelni była sprawdzana przed chwilą.", 6000);
      window.setTimeout(() => void statusQuery.refetch(), 4000);
      window.setTimeout(() => void statusQuery.refetch(), 15000);
    } catch {
      showToast("Nie udało się połączyć z serwerem planu.");
    } finally {
      window.setTimeout(() => setChecking(false), 4000);
    }
  };

  const subscribe = async () => {
    const url = calendarUrl(selection, false);
    try {
      await navigator.clipboard.writeText(url);
      showToast(
        "Skopiowano link do kalendarza. W Kalendarzu Google: Inne kalendarze → „Z adresu URL” i wklej link. Kalendarz będzie się sam aktualizował.",
        14_000,
      );
    } catch {
      window.prompt("Skopiuj link do subskrypcji kalendarza:", url);
    }
  };

  // ------------------------------------------------------------------ render

  const groupLabel = selectionLabel(selection, dimensions);
  const ready = Boolean(plan);

  return (
    <div className="min-h-screen bg-sand font-body text-ink">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-6 px-4 pb-[72px] pt-8 sm:px-5 sm:pt-10">
        <Header plan={plan} sources={sources} status={status} checking={checking} onCheck={checkNow} />

        <Notices sources={sources} status={status} />

        {ready && <GroupPicker dimensions={dimensions} selection={selection} onSelect={selectOption} />}

        {!ready && planQuery.isError && (
          <div className="flex flex-col items-start gap-3 rounded-3xl border border-line bg-linen p-6">
            <div className="font-heading text-xl font-bold">Nie udało się pobrać planu</div>
            <div className="text-sm text-muted">{planQuery.error instanceof Error ? planQuery.error.message : "Błąd połączenia."}</div>
            <button
              type="button"
              onClick={() => void planQuery.refetch()}
              className="h-10 cursor-pointer rounded-full border border-rule bg-linen px-4 text-sm font-bold text-ink"
            >
              Spróbuj ponownie
            </button>
          </div>
        )}
        {!ready && !planQuery.isError && (
          <div className="rounded-3xl border border-line bg-linen p-6 text-sm font-semibold text-muted">Ładowanie planu…</div>
        )}

        {ready && (
          <>
            <Overview
              next={next}
              nextLive={nextLive}
              today={today}
              groupLabel={groupLabel}
              stats={stats}
              hoursOnsite={hoursOnsite}
              hoursRemote={hoursRemote}
            />

            <Toolbar
              view={view}
              onView={setView}
              showPast={showPast}
              onTogglePast={() => setShowPast((value) => !value)}
              icsHref={calendarUrl(selection, true)}
              onSubscribe={subscribe}
            />

            {(isDay || isWeek) && (
              <section className="flex flex-col gap-3">
                <Navigator
                  label={navLabel}
                  sub={navSub}
                  onPrev={() => navigate(-1)}
                  onNext={() => navigate(1)}
                  onToday={() => setCursor(today)}
                  onNextClass={() => next && setCursor(next.e.date)}
                />
                {isDay && <DayView items={dayItems} range={range} emptyHint={emptyHint} />}
                {isWeek && <WeekView columns={weekColumns} range={range} onOpenDay={openDay} />}
              </section>
            )}

            {view === "lista" && <ListView byDay={byDay} today={today} showPast={showPast} onOpenDay={openDay} />}

            {view === "kalendarz" && (
              <MonthView
                byDay={byDay}
                months={months}
                today={today}
                showWeekends={showWeekends}
                legend={stats.map((stat) => ({ short: stat.short, color: stat.color }))}
                onOpenDay={openDay}
              />
            )}
          </>
        )}

        <footer className="flex flex-col gap-1.5 border-t border-[#ddd3bf] pt-5 text-[13px] leading-normal text-muted">
          <div className="font-bold text-ink">Proszę śledzić na bieżąco plan zajęć. Uczelnia zastrzega sobie możliwość wprowadzenia zmian.</div>
          {plan?.dimensions.some((dim) => dim.id === "group") && (
            <div>Ćwiczenia z planu zajęć przypisane do numeru grupy (np. „1”) dotyczą obu podgrup (1a i 1b).</div>
          )}
          {plan?.meta.notes.map((note) => <div key={note}>{note}</div>)}
          <div>
            Plan aktualizuje się automatycznie na podstawie plików ze{" "}
            <a href={status?.sync.page_url ?? "https://wnoz.uni.opole.pl/plany-zajec/"} target="_blank" rel="noreferrer">
              strony Wydziału Nauk o Zdrowiu UO
            </a>
            {sources.length ? ": " : "."}
            {sources.map((source, index) => (
              <span key={source.id}>
                {index > 0 ? ", " : ""}
                {source.url ? (
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {source.name}
                  </a>
                ) : (
                  source.name
                )}
              </span>
            ))}
            {sources.length ? "." : ""}
          </div>
        </footer>
      </div>

      <Toast message={toast} onClose={() => setToast(null)} />
    </div>
  );
}
