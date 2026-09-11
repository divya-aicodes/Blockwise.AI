import { CheckCircle2, ScanLine } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import ConflictTimeline from "./ConflictTimeline";
export default function ConflictPanel() {
  const s = useAppStore();
  if (!s.maintenance) return null;
  return (
    <section className="conflict-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">01 / SCHEDULE CHECK</span>
          <h2>
            Train–maintenance conflicts{" "}
            {s.conflicts && (
              <span className="count">{s.conflicts.conflict_count}</span>
            )}
          </h2>
        </div>
        <button
          className="secondary"
          disabled={!!s.busy}
          onClick={() => void s.detect()}
        >
          <ScanLine size={15} />
          {s.conflicts ? "Check again" : "Detect conflicts"}
        </button>
      </div>
      {s.conflicts ? (
        s.conflicts.conflict_count ? (
          <ConflictTimeline data={s.conflicts} maintenance={s.maintenance} />
        ) : (
          <div className="inline-empty">
            <CheckCircle2 size={20} />
            <span>No train-maintenance overlap detected in this window.</span>
          </div>
        )
      ) : (
        <div className="inline-empty">
          <ScanLine size={22} />
          <span>Check the preferred window against section occupancy.</span>
        </div>
      )}
    </section>
  );
}
