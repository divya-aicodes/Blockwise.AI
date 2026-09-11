import { useState, useCallback } from "react";
import { Check, CheckCircle2, Pencil, X, ShieldCheck } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { clock, dateLabel } from "../lib";
import Modal from "./Modal";
export default function ApprovalButtons() {
  const s = useAppStore(),
    [confirm, setConfirm] = useState(false);
  const close = useCallback(() => setConfirm(false), []);
  const plan = s.plans.find((p) => p.plan_id === s.selectedPlanId);
  if (!plan) return null;
  const result = s.simulations[plan.plan_id],
    decision = s.decisions[plan.plan_id];
  const eligible =
    result &&
    result.kpis.maintenance_completed &&
    result.kpis.conflicts_detected === 0 &&
    plan.safety_conflicts === 0;
  async function approve() {
    if (await s.decide("APPROVED")) setConfirm(false);
  }
  return (
    <section className="approval-panel">
      <span className="eyebrow">HUMAN DECISION</span>
      {decision ? (
        <div className={"decision-state " + decision.decision.toLowerCase()}>
          <CheckCircle2 size={22} />
          <h3>
            {decision.decision === "APPROVED"
              ? "MAINTENANCE PLAN APPROVED"
              : decision.decision === "REJECTED"
                ? "PLAN REJECTED"
                : "MODIFICATION REQUESTED"}
          </h3>
          <p>Human decision recorded · {decision.decision_id}</p>
          <small>
            {dateLabel(decision.recorded_at)} · {clock(decision.recorded_at)}{" "}
            IST
          </small>
          {decision.decision === "APPROVED" && (
            <p>
              This records a planning decision. Railway execution has not
              started.
            </p>
          )}
        </div>
      ) : (
        <>
          <h3>
            Decision support.
            <br />
            Human approval required.
          </h3>
          <p>
            Review the selected plan and its simulation before recording a
            decision.
          </p>
        </>
      )}
      {!eligible && !decision && (
        <p className="notice">
          Simulate this plan with completed maintenance and zero unresolved
          conflicts to enable approval.
        </p>
      )}
      <div className="approval-actions">
        <button
          className="approve"
          disabled={!eligible || !!s.busy || decision?.decision === "APPROVED"}
          onClick={() => setConfirm(true)}
        >
          <Check size={15} />
          Approve
        </button>
        <button
          className="secondary"
          disabled={!!s.busy}
          onClick={async () => {
            if (await s.decide("MODIFY")) {
              if (s.maintenance) s.selectAsset(s.maintenance.asset_id);
              s.openSheet();
            }
          }}
        >
          <Pencil size={14} />
          Modify
        </button>
        <button
          className="reject"
          disabled={!!s.busy || decision?.decision === "REJECTED"}
          onClick={() => void s.decide("REJECTED")}
        >
          <X size={14} />
          Reject
        </button>
      </div>
      {decision?.decision === "REJECTED" && (
        <p className="muted">
          Choose another alternative or modify the requirement to create a new
          plan.
        </p>
      )}
      {s.error && (
        <div className="error" role="alert">
          {s.error}
        </div>
      )}
      {confirm && (
        <Modal title="Review final decision" onClose={close}>
          <div className="decision-summary">
            <ShieldCheck size={30} />
            <h3>
              {plan.plan_id} · {s.maintenance?.section_id}
            </h3>
            <dl className="details-list">
              <div>
                <dt>Window</dt>
                <dd>
                  {clock(plan.maintenance_window.start)}–
                  {clock(plan.maintenance_window.end)} IST
                </dd>
              </div>
              <div>
                <dt>Operating date</dt>
                <dd>{dateLabel(plan.maintenance_window.start)}</dd>
              </div>
              <div>
                <dt>Assigned crew</dt>
                <dd>{plan.assigned_crew_id}</dd>
              </div>
              <div>
                <dt>Planned affected trains</dt>
                <dd>{plan.affected_trains.length}</dd>
              </div>
              <div>
                <dt>Expected train delay</dt>
                <dd>{plan.total_train_delay_min} min</dd>
              </div>
              <div>
                <dt>Simulated train delay</dt>
                <dd>{result?.kpis.total_delay_min} min</dd>
              </div>
              <div>
                <dt>Simulation result</dt>
                <dd>
                  {result?.kpis.maintenance_completed
                    ? "Maintenance completed"
                    : "Incomplete"}
                </dd>
              </div>
              <div>
                <dt>Safety conflicts</dt>
                <dd>{result?.kpis.conflicts_detected}</dd>
              </div>
            </dl>
            <p>
              The backend rechecks the stored plan and retains the decision
              evidence. This is a local demo planning approval.
            </p>
            {s.error && (
              <div className="error" role="alert">
                {s.error}
              </div>
            )}
            <button
              className="approve full"
              disabled={!!s.busy}
              onClick={() => void approve()}
            >
              {s.busy || "Approve plan"}
              <Check size={16} />
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
