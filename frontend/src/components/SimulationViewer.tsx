import { Link } from "react-router-dom";
import { Box, CheckCircle2 } from "lucide-react";
import type { SimulationResult } from "../types";
import { clock } from "../lib";
import KpiCard from "./KpiCard";
export default function SimulationViewer({
  result,
}: {
  result: SimulationResult;
}) {
  return (
    <section className="simulation-result">
      <div className="section-heading">
        <div>
          <span className="eyebrow">
            03 / SIMULATION RESULT · {result.plan_id}
          </span>
          <h2>Plan tested over one operating day</h2>
        </div>
        <Link className="primary" to={`/admin/digital-twin/${result.plan_id}`}>
          <Box size={16} />
          Open digital twin
        </Link>
      </div>
      <div className="simulation-kpis">
        <KpiCard
          label="Total delay"
          value={result.kpis.total_delay_min}
          unit="min"
        />
        <KpiCard
          label="Maximum train delay"
          value={result.kpis.max_single_train_delay_min}
          unit="min"
        />
        <KpiCard
          label="Average delay"
          value={result.kpis.average_delay_min}
          unit="min"
        />
        <KpiCard
          label="Affected trains"
          value={result.kpis.affected_trains_count}
        />
      </div>
      <div className="result-status">
        <CheckCircle2 size={16} />
        <span>
          {result.kpis.conflicts_detected} unresolved safety conflicts
        </span>
        <span>
          Maintenance{" "}
          {result.kpis.maintenance_completed
            ? "completed " + clock(result.kpis.maintenance_completion_time)
            : "incomplete"}
        </span>
      </div>
    </section>
  );
}
