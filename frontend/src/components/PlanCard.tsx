import { Check, ArrowUpRight, Play } from "lucide-react";
import type { AlternativePlan } from "../types";
import { clock, dateLabel } from "../lib";
import { useAppStore } from "../store/useAppStore";
export default function PlanCard({
  plan,
  primary = false,
}: {
  plan: AlternativePlan;
  primary?: boolean;
}) {
  const s = useAppStore(),
    selected = s.selectedPlanId === plan.plan_id;
  return (
    <article
      className={
        (primary ? "recommended-plan" : "alternative-row") +
        (selected ? " selected" : "")
      }
    >
      <button
        className="plan-select"
        onClick={() => s.selectPlan(plan.plan_id)}
        aria-label={"Select " + plan.plan_id}
      >
        <span className="rank-number">
          {String(plan.rank).padStart(2, "0")}
        </span>
        <div>
          {primary && <span className="eyebrow">BEST-RANKED ALTERNATIVE</span>}
          <h3>
            {clock(plan.maintenance_window.start)} <span>—</span>{" "}
            {clock(plan.maintenance_window.end)}
          </h3>
          <small>
            {dateLabel(plan.maintenance_window.start)} · {plan.assigned_crew_id}{" "}
            · <span className="mono">{plan.plan_id}</span>
          </small>
        </div>
        <span className="selection-indicator">
          {selected ? <Check size={15} /> : <ArrowUpRight size={15} />}
        </span>
      </button>
      <div className="plan-metrics">
        <span>
          Train delay
          <b>
            {plan.total_train_delay_min} <small>min</small>
          </b>
        </span>
        <span>
          Affected trains<b>{plan.affected_trains.length}</b>
        </span>
        <span>
          Risk reduction estimate
          <b>
            {plan.risk_reduction_estimate}
            <small> /100</small>
          </b>
        </span>
        <span>
          Score · lower is better<b>{plan.overall_score.toFixed(1)}</b>
        </span>
      </div>
      {primary && (
        <div className="plan-secondary-metrics">
          <span>
            Maintenance delay <b>{plan.maintenance_delay_min} min</b>
          </span>
          <span>
            Crew cost <b>{plan.crew_cost} units</b>
          </span>
          <span>
            Safety conflicts <b>{plan.safety_conflicts}</b>
          </span>
        </div>
      )}
      <div className="plan-actions">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={s.comparison.includes(plan.plan_id)}
            onChange={() => s.toggleCompare(plan.plan_id)}
          />{" "}
          Compare
        </label>
        <button
          className="text-button"
          disabled={!!s.busy}
          onClick={() => void s.simulate(plan.plan_id)}
        >
          <Play size={13} />{" "}
          {s.simulations[plan.plan_id] ? "Simulate again" : "Simulate plan"}
        </button>
      </div>
    </article>
  );
}
