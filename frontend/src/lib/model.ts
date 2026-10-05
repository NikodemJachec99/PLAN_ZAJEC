import type { Dimension, Mode, Plan, PlanEvent, Selection, Subject } from "../types";
import { clock, minutes } from "./time";
import { readStorage, writeStorage } from "./storage";

export const MODE: Record<Mode, { label: string; color: string }> = {
  onsite: { label: "Stacjonarnie", color: "#355f48" },
  remote: { label: "Zdalnie · MS Teams", color: "#2f5f8a" },
  unassigned: { label: "Sala nieprzypisana", color: "#8a8373" },
};

export interface Palette {
  c: string;
  dot: string;
  bg: string;
}

const NEUTRAL: Palette = { c: "#4a463e", dot: "#8a8373", bg: "#ece5d6" };

export function palette(subject: Subject | undefined): Palette {
  if (!subject || subject.hue === null || subject.hue === undefined) return NEUTRAL;
  const h = subject.hue;
  return { c: `oklch(0.48 0.12 ${h})`, dot: `oklch(0.7 0.13 ${h})`, bg: `oklch(0.93 0.04 ${h})` };
}

/** An event enriched with everything the views need (mirrors the design's decorate()). */
export interface Item {
  e: PlanEvent;
  a: number; // start minute
  b: number; // end minute
  title: string;
  short: string;
  type: string;
  typeShort: string;
  where: string;
  whereShort: string;
  place: string;
  who: string;
  note: string;
  time: string;
  dur: string;
  modeLabel: string;
  modeShort: string;
  modeBg: string;
  pal: Palette;
  hours: number;
}

function audience(event: PlanEvent): string {
  if (event.kind === "practical") return "";
  if (event.groups.includes("*")) return "Cały rok";
  return event.group ? `Grupa ${event.group}` : "";
}

export function decorate(event: PlanEvent, subjects: Map<string, Subject>): Item {
  const subject = subjects.get(event.subject_key);
  const a = minutes(event.start);
  const b = minutes(event.end);
  const hours = event.parts.reduce((sum, [start, end]) => sum + (minutes(end) - minutes(start)) / 60, 0) || (b - a) / 60;
  const modeLabel =
    event.mode === "remote" ? (event.where_short === "Teams" ? MODE.remote.label : "Zdalnie") : MODE[event.mode].label;
  const notes = [audience(event)];
  if (event.parts.length > 1) {
    notes.push(`${event.parts.length} bloki: ${event.parts.map(([s, e]) => `${clock(s)}–${clock(e)}`).join(", ")}`);
  }
  if (event.note) notes.push(event.note);
  return {
    e: event,
    a,
    b,
    title: event.subject,
    short: subject?.short || event.subject,
    type: event.type_label || event.type,
    typeShort: event.type_short || event.type,
    where: event.where,
    whereShort: event.where_short,
    place: event.place,
    who: event.instructor,
    note: notes.filter(Boolean).join(" · "),
    time: `${clock(event.start)} – ${clock(event.end)}`,
    dur: `${String(Math.round(((b - a) / 60) * 10) / 10).replace(".", ",")} h`,
    modeLabel,
    modeShort: modeLabel.replace(" · MS Teams", ""),
    modeBg: MODE[event.mode].color,
    pal: palette(subject),
    hours,
  };
}

// ----------------------------------------------------------------------------- groups

const STORAGE_KEYS: Record<string, string> = {
  group: "planzp-group",
  lek: "planzp-lang",
  "cw-a": "planzp-sem",
};

function storageKey(dimensionId: string): string {
  return STORAGE_KEYS[dimensionId] ?? `planzp-dim-${dimensionId}`;
}

export function loadSelection(dimensions: Dimension[]): Selection {
  const selection: Selection = {};
  dimensions.forEach((dim) => {
    const stored = readStorage(storageKey(dim.id));
    const match = dim.options.find((option) => option.toLowerCase() === (stored ?? "").toLowerCase());
    if (match) selection[dim.id] = match;
    else if (dim.options.length) selection[dim.id] = dim.options[0];
  });
  return selection;
}

export function saveSelection(dimensionId: string, value: string): void {
  writeStorage(storageKey(dimensionId), value);
}

export function matches(event: PlanEvent, selection: Selection): boolean {
  const tokens = event.groups.length ? event.groups : ["*"];
  if (tokens.includes("*")) return true;
  const group = selection.group;
  if (group) {
    if (tokens.includes(group)) return true;
    const number = group.match(/^\d+/)?.[0];
    if (number && tokens.includes(number)) return true;
  }
  return Object.entries(selection).some(([key, value]) => key !== "group" && tokens.includes(value));
}

export function selectionLabel(selection: Selection, dimensions: Dimension[]): string {
  return dimensions.map((dim) => selection[dim.id]).filter(Boolean).join(" · ");
}

/** Group options "1a","1b","2c"... arranged as cards per group number (design: "Grupa 1"). */
export function groupCards(options: string[]): { num: string; subs: string[] }[] {
  const cards: { num: string; subs: string[] }[] = [];
  options.forEach((option) => {
    const num = option.match(/^\d+/)?.[0] ?? option;
    const card = cards.find((item) => item.num === num);
    if (card) card.subs.push(option);
    else cards.push({ num, subs: [option] });
  });
  return cards;
}

// ----------------------------------------------------------------------------- layout

export interface Placed extends Item {
  lane: number;
  lanes: number;
}

/** Side-by-side lanes for overlapping events (same algorithm as the design). */
export function layoutLanes(items: Item[]): Placed[] {
  const result: Placed[] = [];
  let cluster: Item[] = [];
  let end = -1;
  const flush = () => {
    const lanes: number[] = [];
    const placed = cluster.map((item) => {
      let lane = lanes.findIndex((laneEnd) => laneEnd <= item.a);
      if (lane < 0) {
        lane = lanes.length;
        lanes.push(0);
      }
      lanes[lane] = item.b;
      return { ...item, lane, lanes: 0 };
    });
    placed.forEach((item) => result.push({ ...item, lanes: lanes.length }));
    cluster = [];
  };
  [...items]
    .sort((x, y) => x.a - y.a || x.b - y.b)
    .forEach((item) => {
      if (cluster.length && item.a >= end) flush();
      cluster.push(item);
      end = cluster.length === 1 ? item.b : Math.max(end, item.b);
    });
  if (cluster.length) flush();
  return result;
}

/** Visible hour range: 7:00-21:00 like the design, widened if anything falls outside it. */
export function hourRange(plan: Plan | undefined): { start: number; end: number } {
  let start = 7 * 60;
  let end = 21 * 60;
  plan?.events.forEach((event) => {
    start = Math.min(start, Math.floor(minutes(event.start) / 60) * 60);
    end = Math.max(end, Math.ceil(minutes(event.end) / 60) * 60);
  });
  return { start, end: Math.min(end, 24 * 60) };
}

export type Size = "tiny" | "small" | "big";

export function sizeFor(px: number, bigMin: number): Size {
  if (px < 64) return "tiny";
  return px >= bigMin ? "big" : "small";
}
