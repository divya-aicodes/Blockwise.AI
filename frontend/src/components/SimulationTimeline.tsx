import { useMemo } from "react";
import type { SimulationResult } from "../types";
import { clock } from "../lib";
export default function SimulationTimeline({
  result,
  now,
  onSeek,
}: {
  result: SimulationResult;
  now: number;
  onSeek: (n: number) => void;
}) {
  const events = useMemo(() => {
    const trainEvents = result.train_results.flatMap((t) =>
      t.section_events.flatMap((e) => [
        {
          time: Date.parse(e.simulated_entry_time),
          label: `${t.train_id} entered ${e.section_id}`,
          kind: "TRAIN ENTRY",
        },
        {
          time: Date.parse(e.simulated_exit_time),
          label: `${t.train_id} exited ${e.section_id}`,
          kind: "TRAIN EXIT",
        },
      ]),
    );
    const m = result.maintenance;
    return [
      ...trainEvents,
      ...(m.simulated_start
        ? [
            {
              time: Date.parse(m.simulated_start),
              label: "Maintenance started · " + result.section_id,
              kind: "MAINTENANCE",
            },
          ]
        : []),
      ...(m.simulated_end
        ? [
            {
              time: Date.parse(m.simulated_end),
              label: "Maintenance completed · " + result.section_id,
              kind: "MAINTENANCE",
            },
          ]
        : []),
    ].sort((a, b) => a.time - b.time);
  }, [result]);
  return (
    <section className="event-timeline">
      <div className="section-heading">
        <h2>Simulation event log</h2>
        <span className="muted text-sm">
          {events.length} recorded events · Select to seek
        </span>
      </div>
      <div className="event-list">
        {events.map((e, i) => (
          <button
            key={i}
            className={e.time <= now ? "occurred" : ""}
            onClick={() => onSeek(e.time)}
          >
            <span className="mono">{clock(e.time)}</span>
            <span
              className={
                "event-kind " + (e.kind === "MAINTENANCE" ? "maintenance" : "")
              }
            >
              {e.kind}
            </span>
            <span>{e.label}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
