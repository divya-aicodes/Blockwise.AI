import type { Section, SimulationResult, Train } from "./types";
export const sections: Section[] = [
  {
    id: "SEC-NDLS-RE",
    from: "NDLS",
    to: "RE",
    distance: 84,
    start: 0,
    end: 84,
  },
  {
    id: "SEC-RE-AWR",
    from: "RE",
    to: "AWR",
    distance: 74,
    start: 84,
    end: 158,
  },
  {
    id: "SEC-AWR-BKI",
    from: "AWR",
    to: "BKI",
    distance: 61,
    start: 158,
    end: 219,
  },
  {
    id: "SEC-BKI-JP",
    from: "BKI",
    to: "JP",
    distance: 90,
    start: 219,
    end: 309,
  },
];
export const stations = [
  { code: "NDLS", name: "New Delhi", km: 0 },
  { code: "RE", name: "Rewari", km: 84 },
  { code: "AWR", name: "Alwar", km: 158 },
  { code: "BKI", name: "Bandikui", km: 219 },
  { code: "JP", name: "Jaipur", km: 309 },
];
export const riskColors = {
  LOW: "#70ae92",
  MEDIUM: "#d6b16b",
  HIGH: "#d68c5e",
  CRITICAL: "#db6b71",
};
export const titleCase = (s: string) =>
  s
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
export const clock = (s: string | number | null) =>
  s === null
    ? "—"
    : new Intl.DateTimeFormat("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Kolkata",
      }).format(new Date(s));
export const dateLabel = (s: string) =>
  new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(new Date(s));
export const operatingDate = (s: string) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(s));
export function defaultWindow() {
  const tomorrow = new Date(Date.now() + 86400000);
  const day = operatingDate(tomorrow.toISOString());
  return {
    earliest_start_time: day + "T06:00",
    preferred_start_time: day + "T08:00",
    latest_end_time: day + "T22:00",
  };
}
export const toIST = (s: string) => (s.length === 16 ? s + ":00+05:30" : s);
export const localInput = (s: string) =>
  new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
    .format(new Date(s))
    .replace(" ", "T");
export function simulationBounds(s: SimulationResult): [number, number] {
  const start = Date.parse(s.simulation_date + "T00:00:00+05:30");
  return [start, start + 86400000];
}
export interface TrainPosition {
  km: number;
  state: "MOVING" | "WAITING";
  section: string;
  waitMinutes: number;
}
export function trainPosition(train: Train, now: number): TrainPosition | null {
  for (let i = 0; i < train.section_events.length; i++) {
    const e = train.section_events[i];
    const section = sections.find((s) => s.id === e.section_id);
    if (!section) continue;
    const entry = Date.parse(e.simulated_entry_time),
      exit = Date.parse(e.simulated_exit_time);
    if (now >= entry && now < exit)
      return {
        km:
          section.start +
          ((section.end - section.start) * (now - entry)) / (exit - entry),
        state: "MOVING",
        section: e.section_id,
        waitMinutes: 0,
      };
    const previous = train.section_events[i - 1];
    const available = Math.max(
      Date.parse(e.scheduled_entry_time),
      previous ? Date.parse(previous.simulated_exit_time) : 0,
    );
    if (now >= available && now < entry)
      return {
        km: section.start,
        state: "WAITING",
        section: e.section_id,
        waitMinutes: Math.floor((now - available) / 60000),
      };
  }
  return null;
}
