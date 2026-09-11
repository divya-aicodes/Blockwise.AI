import { Link } from "react-router-dom";
import { ArrowRight, GitCompareArrows, RotateCcw } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { clock, dateLabel } from "../lib";
import ConflictPanel from "../components/ConflictPanel";
import PlanCard from "../components/PlanCard";
import PlanComparison from "../components/PlanComparison";
import SimulationViewer from "../components/SimulationViewer";
import ApprovalButtons from "../components/ApprovalButtons";
import FeedbackPanel from "../components/FeedbackPanel";
export default function PlanPage() {
  const s = useAppStore(),
    m = s.maintenance;
  const plan = s.plans.find((p) => p.plan_id === s.selectedPlanId),
    result = plan ? s.simulations[plan.plan_id] : undefined;
  if (!m)
    return (
      <div className="page empty-state">
        <GitCompareArrows size={34} />
        <h1>A window for better maintenance.</h1>
        <p>
          Select an asset and create a requirement to open the planning
          workspace.
        </p>
        <Link className="primary" to="/map">
          Select an asset <ArrowRight size={16} />
        </Link>
      </div>
    );
  return (
    <div className="page plan-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">MAINTENANCE DECISION WORKSPACE</span>
          <h1>
            Operations planning
            <span className="heading-mono">{m.maintenance_id}</span>
          </h1>
          <p>Resolve conflicts. Compare trade-offs. Test the decision.</p>
        </div>
        <button
          className="secondary"
          onClick={() => {
            s.selectAsset(m.asset_id);
            s.openSheet();
          }}
          disabled={!!s.busy}
        >
          <RotateCcw size={14} />
          Revise requirement
        </button>
      </div>
      <div className="planning-strip">
        <span>
          ASSET<b className="mono">{m.asset_id}</b>
        </span>
        <span>
          SECTION<b className="mono">{m.section_id}</b>
        </span>
        <span>
          URGENCY<b>{m.urgency}</b>
        </span>
        <span>
          REQUIRED SKILL<b>{m.required_skill}</b>
        </span>
        <span>
          MINIMUM DURATION<b>{m.minimum_duration_min} min</b>
        </span>
        <span>
          PLANNING HORIZON
          <b>
            {clock(m.earliest_start_time)}—{clock(m.latest_end_time)}
          </b>
          <small>
            {dateLabel(m.earliest_start_time)} – {dateLabel(m.latest_end_time)}
          </small>
        </span>
      </div>
      {s.busy && (
        <div className="busy-banner" role="status">
          <span className="spinner" />
          {s.busy}
        </div>
      )}
      {s.error && (
        <div className="error" role="alert">
          {s.error}
        </div>
      )}
      <div className="planning-layout">
        <div>
          <ConflictPanel />
          <section className="alternatives-panel">
            <div className="section-heading">
              <div>
                <span className="eyebrow">02 / FEASIBLE ALTERNATIVES</span>
                <h2>Find the right maintenance window</h2>
              </div>
              <button
                className="primary"
                disabled={!!s.busy}
                onClick={() => void s.generate()}
              >
                <GitCompareArrows size={15} />
                {s.plans.length
                  ? "Regenerate alternatives"
                  : "Generate alternatives"}
              </button>
            </div>
            <p className="muted text-sm">
              Ranked by delay, risk and crew trade-offs. Lower scores rank
              first.
            </p>
            {s.plans.length ? (
              <div className="plans-list">
                {s.plans.map((p, i) => (
                  <PlanCard key={p.plan_id} plan={p} primary={i === 0} />
                ))}
              </div>
            ) : (
              <div className="alternatives-empty">
                <span className="outline-number">01 — 05</span>
                <p>
                  Feasible alternatives will appear here after optimization.
                </p>
                <small>
                  The backend selects windows, qualifies crews and calculates
                  delay.
                </small>
              </div>
            )}
          </section>
          <PlanComparison
            plans={s.plans.filter((p) => s.comparison.includes(p.plan_id))}
          />
          {result && plan && (
            <>
              <SimulationViewer result={result} />
              <FeedbackPanel result={result} plan={plan} />
            </>
          )}
        </div>
        <aside className="planning-inspector">
          {plan ? (
            <>
              <span className="eyebrow">SELECTED ALTERNATIVE</span>
              <h2>
                {plan.plan_id}
                <span className="count">Rank {plan.rank}</span>
              </h2>
              <dl className="details-list">
                <div>
                  <dt>Window</dt>
                  <dd>
                    {clock(plan.maintenance_window.start)}—
                    {clock(plan.maintenance_window.end)}
                  </dd>
                </div>
                <div>
                  <dt>Crew</dt>
                  <dd>{plan.assigned_crew_id}</dd>
                </div>
                <div>
                  <dt>Maintenance delay</dt>
                  <dd>{plan.maintenance_delay_min} min</dd>
                </div>
                <div>
                  <dt>Risk reduction estimate</dt>
                  <dd>{plan.risk_reduction_estimate}/100</dd>
                </div>
                <div>
                  <dt>Crew cost</dt>
                  <dd>{plan.crew_cost} units</dd>
                </div>
                <div>
                  <dt>Safety conflicts</dt>
                  <dd>{plan.safety_conflicts}</dd>
                </div>
              </dl>
              <div className="divider" />
              <h3>Affected trains</h3>
              {plan.affected_trains.length ? (
                plan.affected_trains.map((t) => (
                  <div className="train-impact" key={t.train_id}>
                    <span className="mono">
                      {t.train_id}
                      <small>{t.priority} priority</small>
                    </span>
                    <b>+{t.delay_added_min} min</b>
                  </div>
                ))
              ) : (
                <p className="muted">No train delay proposed.</p>
              )}
              <ApprovalButtons />
            </>
          ) : (
            <>
              <span className="eyebrow">PLANNING CONTEXT</span>
              <h2>Safety is a constraint.</h2>
              <p>
                The solver must fit qualified crews and train movements around
                the maintenance window.
              </p>
              <div className="divider" />
              <dl className="details-list">
                <div>
                  <dt>Train delay limit</dt>
                  <dd>360 min</dd>
                </div>
                <div>
                  <dt>Alternatives requested</dt>
                  <dd>5</dd>
                </div>
                <div>
                  <dt>Network</dt>
                  <dd>Linear corridor</dd>
                </div>
              </dl>
              <p className="muted">
                If no feasible plan exists, revise the supported planning
                inputs.
              </p>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
