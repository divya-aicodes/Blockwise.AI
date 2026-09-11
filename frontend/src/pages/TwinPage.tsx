import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, Box, Clock3 } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { clock, dateLabel, simulationBounds, trainPosition } from "../lib";
import type { SimulationResult, AlternativePlan } from "../types";
import DigitalTwinScene from "../components/DigitalTwinScene";
import TwinPlaybackControls from "../components/TwinPlaybackControls";
import SimulationTimeline from "../components/SimulationTimeline";
import ApprovalButtons from "../components/ApprovalButtons";
import FeedbackPanel from "../components/FeedbackPanel";
import KpiCard from "../components/KpiCard";
function Playback({
  result,
  plan,
}: {
  result: SimulationResult;
  plan: AlternativePlan;
}) {
  const bounds = useMemo(() => simulationBounds(result), [result]);
  const [now, setNow] = useState(bounds[0]),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1);
  useEffect(() => {
    if (!playing) return;
    let id = 0,
      last = performance.now();
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
  const m = result.maintenance;
  const started = !!m.simulated_start && now >= Date.parse(m.simulated_start),
    completed = !!m.simulated_end && now >= Date.parse(m.simulated_end);
  const state = completed ? "COMPLETED" : started ? "ACTIVE" : "SCHEDULED";
  const visible = result.train_results
    .map((t) => ({ train: t, position: trainPosition(t, now) }))
    .filter((t) => t.position);
  return (
    <>
      <div className="twin-kpis">
        <KpiCard
          label="Total delay"
          value={result.kpis.total_delay_min}
          unit="min"
        />
        <KpiCard
          label="Maximum delay"
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
        <KpiCard
          label="Completion"
          value={clock(result.kpis.maintenance_completion_time)}
        />
        <span className="safety-counter">
          {result.kpis.conflicts_detected}{" "}
          <small>unresolved safety conflicts</small>
        </span>
      </div>
      <div className="twin-layout">
        <section className="twin-main">
          <DigitalTwinScene result={result} now={now} />
          <TwinPlaybackControls
            playing={playing}
            onToggle={() => {
              if (now >= bounds[1]) setNow(bounds[0]);
              setPlaying((p) => !p);
            }}
            onRestart={() => seek(bounds[0])}
            onStep={(n) => seek(now + n * 60000)}
            speed={speed}
            setSpeed={setSpeed}
            now={now}
            bounds={bounds}
            onScrub={seek}
          />
          <SimulationTimeline result={result} now={now} onSeek={seek} />
        </section>
        <aside className="twin-inspector">
          <span className="eyebrow">OPERATIONAL INSPECTOR</span>
          <div className="current-time">
            <Clock3 size={19} />
            <strong className="mono">{clock(now)}</strong>
            <span>IST</span>
          </div>
          <div className="section-heading">
            <h3>Maintenance</h3>
            <span className={"state-label " + state.toLowerCase()}>
              {state}
            </span>
          </div>
          <p className="mono text-sm">{result.section_id}</p>
          <dl className="details-list">
            <div>
              <dt>Predicted duration</dt>
              <dd>{m.predicted_duration_min} min</dd>
            </div>
            <div>
              <dt>Simulated duration</dt>
              <dd>{m.simulated_duration_min} min</dd>
            </div>
            <div>
              <dt>Actual simulated start</dt>
              <dd>{clock(m.simulated_start)}</dd>
            </div>
            <div>
              <dt>Actual simulated end</dt>
              <dd>{clock(m.simulated_end)}</dd>
            </div>
          </dl>
          <button
            className="secondary full"
            disabled={!m.simulated_start}
            onClick={() => seek(Date.parse(m.simulated_start!))}
          >
            Jump to maintenance <ArrowRight size={14} />
          </button>
          <div className="divider" />
          <h3>
            On the corridor <span className="count">{visible.length}</span>
          </h3>
          {visible.length ? (
            <div className="active-trains">
              {visible.map(({ train, position }) => (
                <div className="train-impact" key={train.train_id}>
                  <span className="mono">
                    {train.train_id}
                    <small>{position?.section}</small>
                  </span>
                  <b className={position?.state === "WAITING" ? "amber" : ""}>
                    {position?.state === "WAITING"
                      ? `${position.waitMinutes} min wait`
                      : "Moving"}
                  </b>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted text-sm">
              No train occupancy or waiting interval at this time.
            </p>
          )}
          <details className="affected-details">
            <summary>
              All affected trains ({result.kpis.affected_trains_count})
            </summary>
            {result.kpis.affected_train_ids.map((id) => (
              <p className="mono text-xs" key={id}>
                {id}
              </p>
            ))}
          </details>
          <p className="muted text-xs">
            Movement between section endpoints is interpolated from returned
            entry and exit times. Waiting is inferred from schedule and entry
            gaps; station dwell is not shown as movement.
          </p>
          <ApprovalButtons />
        </aside>
      </div>
      <FeedbackPanel result={result} plan={plan} />
    </>
  );
}
export default function TwinPage() {
  const s = useAppStore(),
    plan = s.plans.find((p) => p.plan_id === s.selectedPlanId),
    result = plan ? s.simulations[plan.plan_id] : undefined;
  if (!result || !plan)
    return (
      <div className="page empty-state">
        <Box size={34} />
        <h1>Test the plan. See the outcome.</h1>
        <p>
          Simulate a maintenance alternative to unlock event-based corridor
          playback.
        </p>
        <Link className="primary" to="/plan">
          Open planning <ArrowRight size={16} />
        </Link>
      </div>
    );
  return (
    <div className="page twin-page">
      <Link className="back-link" to="/plan">
        <ArrowLeft size={14} /> Back to planning
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">DETERMINISTIC SIMULATION VIEWER</span>
          <h1>
            Digital twin<span className="heading-mono">{result.plan_id}</span>
          </h1>
          <p>
            {dateLabel(result.maintenance.planned_start)} ·{" "}
            {result.kpis.trains_simulated} trains simulated · 24-hour operating
            day
          </p>
        </div>
        <span className="demo-label">STAGE 3 EVENT PLAYBACK</span>
      </div>
      <Playback
        key={result.plan_id + JSON.stringify(result.maintenance)}
        result={result}
        plan={plan}
      />
    </div>
  );
}
