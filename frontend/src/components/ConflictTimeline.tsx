import type { ConflictResponse, MaintenanceRequirement } from "../types";
import { clock } from "../lib";
export default function ConflictTimeline({
  data,
  maintenance,
}: {
  data: ConflictResponse;
  maintenance: MaintenanceRequirement;
}) {
  const start = Date.parse(maintenance.preferred_start_time),
    end = start + maintenance.minimum_duration_min * 60000;
  const lo =
      Math.min(
        start,
        ...data.conflicts.map((c) => Date.parse(c.train_entry_time)),
      ) -
      15 * 60000,
    hi =
      Math.max(
        end,
        ...data.conflicts.map((c) => Date.parse(c.train_exit_time)),
      ) +
      15 * 60000;
  const pct = (n: number) => ((n - lo) / (hi - lo)) * 100;
  return (
    <div className="timeline-scroll">
      <div className="conflict-timeline">
        <div className="timeline-axis">
          <span>OCCUPANCY · IST</span>
          <div>
            {[0, 1, 2, 3, 4].map((i) => (
              <span key={i} style={{ left: i * 25 + "%" }}>
                {clock(lo + ((hi - lo) * i) / 4)}
              </span>
            ))}
          </div>
        </div>
        <div className="timeline-row">
          <span className="mono">
            {maintenance.maintenance_id}
            <small>Maintenance</small>
          </span>
          <div className="timeline-lane">
            <div
              className="maintenance-bar"
              style={{
                left: pct(start) + "%",
                width: pct(end) - pct(start) + "%",
              }}
            >
              {clock(start)}—{clock(end)}
            </div>
          </div>
        </div>
        {data.conflicts.map((c, i) => (
          <div className="timeline-row" key={c.train_id + i}>
            <span className="mono">
              {c.train_id}
              <small>
                {c.train_priority} priority · {c.overlap_duration_min} min
                overlap
              </small>
            </span>
            <div className="timeline-lane">
              <div
                className="occupancy-bar"
                title={`${clock(c.train_entry_time)}–${clock(c.train_exit_time)}`}
                style={{
                  left: pct(Date.parse(c.train_entry_time)) + "%",
                  width:
                    pct(Date.parse(c.train_exit_time)) -
                    pct(Date.parse(c.train_entry_time)) +
                    "%",
                }}
              />
              <div
                className="overlap-bar"
                style={{
                  left: pct(Date.parse(c.overlap_start)) + "%",
                  width:
                    pct(Date.parse(c.overlap_end)) -
                    pct(Date.parse(c.overlap_start)) +
                    "%",
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
