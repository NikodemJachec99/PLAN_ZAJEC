const POLISH_DAY_NAMES = ["Pon", "Wt", "Sr", "Czw", "Pt", "Sob", "Niedz"];

function pad(value: number): string {
  return value.toString().padStart(2, "0");
}

export function parseISODate(value: string): Date {
  return new Date(`${value}T00:00:00`);
}

export function formatISODate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function shiftDate(isoDate: string, days: number): string {
  const date = parseISODate(isoDate);
  date.setDate(date.getDate() + days);
  return formatISODate(date);
}

export function startOfWeek(isoDate: string): string {
  const date = parseISODate(isoDate);
  const day = (date.getDay() + 6) % 7;
  date.setDate(date.getDate() - day);
  return formatISODate(date);
}

export function coerceToWorkday(isoDate: string): string {
  const date = parseISODate(isoDate);
  const day = (date.getDay() + 6) % 7;
  if (day <= 4) {
    return isoDate;
  }
  return shiftDate(isoDate, 4 - day);
}

export function weekRangeLabel(weekStartIso: string): string {
  const start = parseISODate(weekStartIso);
  const end = parseISODate(weekStartIso);
  end.setDate(end.getDate() + 6);
  return `${pad(start.getDate())}.${pad(start.getMonth() + 1)} - ${pad(end.getDate())}.${pad(end.getMonth() + 1)}.${end.getFullYear()}`;
}

export function polishDateLabel(isoDate: string): string {
  const date = parseISODate(isoDate);
  const weekday = POLISH_DAY_NAMES[(date.getDay() + 6) % 7];
  return `${weekday}, ${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}`;
}

export function dayShortLabel(isoDate: string): string {
  const date = parseISODate(isoDate);
  return `${POLISH_DAY_NAMES[(date.getDay() + 6) % 7]} ${date.getDate()}`;
}

export function getTodayInTimezone(timeZone: string): string {
  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });

  const parts = formatter.formatToParts(new Date());
  const year = parts.find((part) => part.type === "year")?.value;
  const month = parts.find((part) => part.type === "month")?.value;
  const day = parts.find((part) => part.type === "day")?.value;

  if (!year || !month || !day) {
    return formatISODate(new Date());
  }

  return `${year}-${month}-${day}`;
}

export function getNowMinutesInTimezone(timeZone: string): { isoDate: string; minutes: number } {
  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  const parts = formatter.formatToParts(new Date());
  const year = parts.find((part) => part.type === "year")?.value ?? "1970";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  const hour = Number(parts.find((part) => part.type === "hour")?.value ?? "0");
  const minute = Number(parts.find((part) => part.type === "minute")?.value ?? "0");

  return {
    isoDate: `${year}-${month}-${day}`,
    minutes: hour * 60 + minute,
  };
}
