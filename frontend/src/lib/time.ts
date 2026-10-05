// Calendar helpers. Dates are handled as "YYYY-MM-DD" strings in the Europe/Warsaw zone.

export const TIMEZONE = "Europe/Warsaw";
export const WD = ["nd", "pn", "wt", "śr", "czw", "pt", "sb"];
export const WDL = ["niedziela", "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota"];
export const MON = [
  "styczeń",
  "luty",
  "marzec",
  "kwiecień",
  "maj",
  "czerwiec",
  "lipiec",
  "sierpień",
  "wrzesień",
  "październik",
  "listopad",
  "grudzień",
];
export const MONG = [
  "stycznia",
  "lutego",
  "marca",
  "kwietnia",
  "maja",
  "czerwca",
  "lipca",
  "sierpnia",
  "września",
  "października",
  "listopada",
  "grudnia",
];

export function parseDay(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function isoDay(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function shift(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

export function mondayOf(date: Date): Date {
  return shift(date, -((date.getDay() + 6) % 7));
}

export function isWeekend(date: Date): boolean {
  return date.getDay() === 0 || date.getDay() === 6;
}

export function minutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

/** "08:00" -> "8:00" (the design shows hours without a leading zero). */
export function clock(hhmm: string): string {
  return hhmm.replace(/^0(\d)/, "$1");
}

export function nowInWarsaw(): { today: string; minutes: number } {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "0";
  const hour = Number(get("hour")) % 24;
  return { today: `${get("year")}-${get("month")}-${get("day")}`, minutes: hour * 60 + Number(get("minute")) };
}

export function plural(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one;
  const lastDigit = n % 10;
  const lastTwo = n % 100;
  return lastDigit >= 2 && lastDigit <= 4 && (lastTwo < 10 || lastTwo >= 20) ? few : many;
}

export function fmtHours(hours: number): string {
  return String(Math.round(hours * 10) / 10).replace(".", ",");
}

export function shortDate(value: string | null): string {
  if (!value) return "";
  const [y, m, d] = value.slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
}

export function dayLong(value: string): string {
  const date = parseDay(value);
  return `${WDL[date.getDay()]}, ${date.getDate()} ${MONG[date.getMonth()]}`;
}

export function timeAgo(iso: string | null, nowIso?: string): string {
  if (!iso) return "jeszcze nie";
  const now = nowIso ? new Date(nowIso).getTime() : Date.now();
  const diff = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  if (diff < 1) return "przed chwilą";
  if (diff < 60) return `${diff} min temu`;
  const hours = Math.round(diff / 60);
  if (hours < 24) return `${hours} ${plural(hours, "godzinę", "godziny", "godzin")} temu`;
  const days = Math.round(hours / 24);
  return `${days} ${plural(days, "dzień", "dni", "dni")} temu`;
}

export function localClock(iso: string | null): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("pl-PL", {
    timeZone: TIMEZONE,
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}
