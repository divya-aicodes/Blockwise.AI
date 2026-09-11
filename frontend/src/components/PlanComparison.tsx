import type { AlternativePlan } from "../types";
import { clock } from "../lib";
export default function PlanComparison({
  plans,
}: {
  plans: AlternativePlan[];
}) {
  if (plans.length < 2) return null;
  const rows: {
    label: string;
    get: (p: AlternativePlan) => number | string;
    best?: "min" | "max";
  }[] = [
    {
      label: "Maintenance window",
      get: (p) =>
        clock(p.maintenance_window.start) +
        "–" +
        clock(p.maintenance_window.end),
    },
    { label: "Crew", get: (p) => p.assigned_crew_id },
    {
      label: "Affected trains",
      get: (p) => p.affected_trains.length,
      best: "min",
    },
    {
      label: "Total train delay · min",
      get: (p) => p.total_train_delay_min,
      best: "min",
    },
    {
      label: "Maintenance delay · min",
      get: (p) => p.maintenance_delay_min,
      best: "min",
    },
    {
      label: "Risk reduction estimate · /100",
      get: (p) => p.risk_reduction_estimate,
      best: "max",
    },
    { label: "Crew cost · units", get: (p) => p.crew_cost, best: "min" },
    { label: "Safety conflicts", get: (p) => p.safety_conflicts, best: "min" },
    { label: "Score", get: (p) => p.overall_score, best: "min" },
  ];
  return (
    <section className="comparison">
      <div className="section-heading">
        <h2>Compare alternatives</h2>
        <span className="muted text-sm">Best values underlined</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Planning measure</th>
              {plans.map((p) => (
                <th key={p.plan_id}>
                  {p.plan_id} · Rank {p.rank}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const values = plans.map(row.get);
              const best = row.best
                ? row.best === "min"
                  ? Math.min(...values.map(Number))
                  : Math.max(...values.map(Number))
                : undefined;
              return (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  {values.map((v, i) => (
                    <td
                      key={plans[i].plan_id}
                      className={v === best ? "best-value" : ""}
                    >
                      {v}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
