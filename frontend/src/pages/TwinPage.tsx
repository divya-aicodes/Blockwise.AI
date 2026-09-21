import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Box,
  CheckCircle2,
  CircleAlert,
  Clock3,
  HardHat,
  ShieldCheck,
  TrainFront,
  Users,
  Wrench,
} from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { clock, dateLabel, simulationBounds, trainPosition } from "../lib";
import type { AlternativePlan, SimulationResult } from "../types";
import DigitalTwinScene from "../components/DigitalTwinScene";
import TwinPlaybackControls from "../components/TwinPlaybackControls";
import SimulationTimeline from "../components/SimulationTimeline";
import ApprovalButtons from "../components/ApprovalButtons";
import FeedbackPanel from "../components/FeedbackPanel";
import KpiCard from "../components/KpiCard";

const executionLabel = (value?: string) =>
  value ? value.replaceAll("_", " ") : "Not selected";

function ReadinessItem({
  ready,
  label,
  detail,
}: {
  ready: boolean;
  label: string;
  detail: string;
}) {
  return (
    <div className={`twin-readiness-item ${ready ? "ready" : "pending"}`}>
      {ready ? <CheckCircle2 size={16} /> : <CircleAlert size={16} />}
      <span>
        <b>{label}</b>
        <small>{detail}</small>
      </span>
    </div>
  );
}

function Playback({
  result,
  plan,
}: {
  result: SimulationResult;
  plan: AlternativePlan;
}) {
  const bounds = useMemo(() => simulationBounds(result), [result]);
  const [now, setNow] = useState(bounds[0]);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  useEffect(() => {
    if (!playing) return;
    let id = 0;
    let last = performance.now();
    const frame = (time: number) => {
      const elapsed = Math.min(time - last, 100);
      last = time;
      setNow((current) => {
        const next = Math.min(current + elapsed * 600 * speed, bounds[1]);
        if (next >= bounds[1]) setPlaying(false);
        return next;
      });
      id = requestAnimationFrame(frame);
    };
    id = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(id);
  }, [playing, speed, bounds]);

  const seek = (value: number) => {
    setPlaying(false);
    setNow(Math.max(bounds[0], Math.min(value, bounds[1])));
  };
  const maintenance = result.maintenance;
  const started = Boolean(
    maintenance.simulated_start && now >= Date.parse(maintenance.simulated_start),
  );
  const completed = Boolean(
    maintenance.simulated_end && now >= Date.parse(maintenance.simulated_end),
  );
  const state = completed ? "COMPLETED" : started ? "ACTIVE" : "SCHEDULED";
  const visible = result.train_results
    .map((train) => ({ train, position: trainPosition(train, now) }))
    .filter((train) => train.position);
  const execution = result.execution_context;
  const resources = execution?.resource_validation;
  const safetyValid =
    execution?.safety_validation.valid ?? result.kpis.conflicts_detected === 0;
  const durationDelta =
    maintenance.simulated_duration_min - maintenance.predicted_duration_min;

  return (
    <>
      <div className="twin-control-layout">
        <section className="twin-stage">
          <div className="twin-stage-heading">
            <div>
              <span className="eyebrow">INTEGRATED 4D CORRIDOR VIEW</span>
              <h2>Live operating scenario</h2>
            </div>
            <div className="twin-live-clock" aria-label="Current simulation time">
              <span className={playing ? "pulse-dot active" : "pulse-dot"} />
              <Clock3 size={15} />
              <strong className="mono">{clock(now)}</strong>
              <small>IST · {state}</small>
            </div>
          </div>
          <DigitalTwinScene result={result} now={now} />
          <TwinPlaybackControls
            playing={playing}
            onToggle={() => {
              if (now >= bounds[1]) setNow(bounds[0]);
              setPlaying((current) => !current);
            }}
            onRestart={() => seek(bounds[0])}
            onStep={(minutes) => seek(now + minutes * 60000)}
            speed={speed}
            setSpeed={setSpeed}
            now={now}
            bounds={bounds}
            onScrub={seek}
          />
        </section>

        <aside className="twin-command-rail">
          <section className="twin-side-card twin-metric-card">
            <div className="section-heading">
              <div>
                <span className="eyebrow">SIMULATION OUTPUT</span>
                <h2>Key metrics</h2>
              </div>
              <Activity size={18} />
            </div>
            <div className="twin-kpis">
              <KpiCard label="Total delay" value={result.kpis.total_delay_min} unit="min" />
              <KpiCard label="Maximum delay" value={result.kpis.max_single_train_delay_min} unit="min" />
              <KpiCard label="Average delay" value={result.kpis.average_delay_min} unit="min" />
              <KpiCard label="Affected trains" value={result.kpis.affected_trains_count} />
              <KpiCard
                label="Completion"
                value={clock(result.kpis.maintenance_completion_time || maintenance.simulated_end)}
              />
              <div className={`twin-safety-kpi ${safetyValid ? "safe" : "unsafe"}`}>
                <ShieldCheck size={18} />
                <span>Safety conflicts</span>
                <strong className="mono">{result.kpis.conflicts_detected}</strong>
              </div>
            </div>
          </section>

          <section className="twin-side-card twin-maintenance-card">
            <div className="section-heading">
              <div>
                <span className="eyebrow">MAINTENANCE BLOCK</span>
                <h2>{result.section_id}</h2>
              </div>
              <span className={`state-label ${state.toLowerCase()}`}>{state}</span>
            </div>
            <dl className="twin-compact-details">
              <div><dt>Plan</dt><dd>{result.plan_id}</dd></div>
              <div><dt>Window</dt><dd>{clock(maintenance.planned_start)}–{clock(maintenance.planned_end)}</dd></div>
              <div><dt>Predicted duration</dt><dd>{maintenance.predicted_duration_min} min</dd></div>
              <div><dt>Simulated duration</dt><dd>{maintenance.simulated_duration_min} min</dd></div>
              <div><dt>Duration variance</dt><dd className={durationDelta > 0 ? "amber" : "green"}>{durationDelta > 0 ? "+" : ""}{durationDelta} min</dd></div>
            </dl>
            <button
              className="secondary full"
              disabled={!maintenance.simulated_start}
              onClick={() => seek(Date.parse(maintenance.simulated_start!))}
            >
              Jump to maintenance <ArrowRight size={14} />
            </button>
          </section>

          <section className="twin-side-card twin-execution-card">
            <div className="section-heading">
              <div>
                <span className="eyebrow">EXECUTION READINESS</span>
                <h2>{executionLabel(execution?.execution_mode)}</h2>
              </div>
              <HardHat size={18} />
            </div>
            <div className="twin-assignment-line">
              <Users size={15} />
              <span>Assigned crew</span>
              <b className="mono">{execution?.assigned_crew_id || "Pending"}</b>
            </div>
            <div className="twin-readiness-list">
              <ReadinessItem
                ready={Boolean(resources?.manpower_available)}
                label="Manpower"
                detail={resources ? `${resources.assigned_manpower} assigned` : "Work order not linked"}
              />
              <ReadinessItem
                ready={Boolean(resources?.equipment_available)}
                label="Equipment"
                detail={resources?.required_equipment.length ? resources.required_equipment.join(", ") : "No evidence recorded"}
              />
              <ReadinessItem
                ready={Boolean(resources?.materials_available)}
                label="Materials"
                detail={resources?.required_materials.length ? resources.required_materials.join(", ") : "No evidence recorded"}
              />
              <ReadinessItem
                ready={safetyValid}
                label="Safety validation"
                detail={safetyValid ? "Zero unresolved conflicts" : "Execution blocked"}
              />
            </div>
            <div className={`twin-executable ${execution?.executable ? "ready" : "blocked"}`}>
              {execution?.executable ? <CheckCircle2 size={17} /> : <CircleAlert size={17} />}
              <span>
                <b>{execution?.executable ? "Execution ready" : "Not execution ready"}</b>
                <small>{execution ? execution.resource_validation.validation_status : "Create and assign an approved work order"}</small>
              </span>
            </div>
          </section>
        </aside>
      </div>

      <div className="twin-analysis-grid">
        <SimulationTimeline result={result} now={now} onSeek={seek} />
        <section className="twin-live-card">
          <div className="section-heading">
            <div>
              <span className="eyebrow">AT {clock(now)} IST</span>
              <h2>Corridor occupancy</h2>
            </div>
            <TrainFront size={19} />
          </div>
          <div className="twin-occupancy-summary">
            <strong className="mono">{visible.length}</strong>
            <span>trains currently represented on the corridor</span>
          </div>
          {visible.length ? (
            <div className="active-trains">
              {visible.map(({ train, position }) => (
                <article
                  className="train-impact"
                  key={train.train_id}
                >
                  <span className="mono">{train.train_id}<small>{position?.section}</small></span>
                  <b className={position?.state === "WAITING" ? "amber" : "green"}>
                    {position?.state === "WAITING" ? `${position.waitMinutes} min wait` : "Moving"}
                  </b>
                </article>
              ))}
            </div>
          ) : (
            <div className="twin-empty-occupancy">
              <TrainFront size={24} />
              <p>No train occupancy or waiting interval at this simulation time.</p>
            </div>
          )}
          <div className="twin-impact-summary">
            <span><Wrench size={14} /> Affected trains</span>
            <b>{result.kpis.affected_trains_count}</b>
          </div>
          <p className="muted text-xs">
            Movement is interpolated from simulated section entry and exit times. This is synthetic decision-support playback, not live signalling data.
          </p>
        </section>
      </div>

      <FeedbackPanel result={result} plan={plan} />
      <section className="twin-decision-panel">
        <ApprovalButtons />
      </section>
    </>
  );
}

export default function TwinPage() {
  const store = useAppStore();
  const plan = store.plans.find((candidate) => candidate.plan_id === store.selectedPlanId);
  const result = plan ? store.simulations[plan.plan_id] : undefined;

  if (!result || !plan) {
    return (
      <div className="page empty-state">
        <Box size={34} />
        <h1>Test the plan. See the outcome.</h1>
        <p>Simulate a maintenance alternative to unlock the interactive 4D corridor.</p>
        <Link className="primary" to="/admin/planning/new">Open planning <ArrowRight size={16} /></Link>
      </div>
    );
  }

  return (
    <div className="page twin-page twin-command-page">
      <Link className="back-link" to="/admin/planning/new"><ArrowLeft size={14} /> Back to planning</Link>
      <div className="page-heading twin-page-heading">
        <div>
          <span className="eyebrow">DIGITAL TWIN · 3D CORRIDOR + SIMULATION TIME</span>
          <h1>Integrated operations twin<span className="heading-mono">{result.plan_id}</span></h1>
          <p>
            {dateLabel(result.maintenance.planned_start)} · {result.kpis.trains_simulated} trains simulated · New Delhi to Jaipur · deterministic 24-hour scenario
          </p>
        </div>
        <div className="twin-heading-status">
          <span className="demo-label">SYNTHETIC DIGITAL TWIN</span>
          <span className="twin-seed mono">SEED {result.random_seed}</span>
        </div>
      </div>
      <Playback key={result.plan_id + JSON.stringify(result.maintenance)} result={result} plan={plan} />
    </div>
  );
}
