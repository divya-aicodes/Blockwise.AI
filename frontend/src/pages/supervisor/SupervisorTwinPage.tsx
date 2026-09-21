import { useEffect, useState } from "react";
import { Activity, ArrowLeft, CheckCircle2, CircleAlert, ShieldCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { simulationApi } from "../../api/simulation";
import { workOrdersApi } from "../../api/workOrders";
import RailwayCorridor from "../../components/RailwayCorridor";
import { operatingDate } from "../../lib";
import { useAppStore } from "../../store/useAppStore";
import type { SimulationResult } from "../../types";
import type { ExecutionSummary } from "../../types/api";

export default function SupervisorTwinPage() {
  const { id = "" } = useParams();
  const assets = useAppStore((state) => state.assets);
  const selectAsset = useAppStore((state) => state.selectAsset);
  const initialize = useAppStore((state) => state.initialize);
  const [summary, setSummary] = useState<ExecutionSummary | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void initialize();
    workOrdersApi.summary(id)
      .then(async (data) => {
        setSummary(data);
        const date = operatingDate(data.work_order.planned_start || new Date().toISOString());
        setResult(await simulationApi.run({ plan_id: data.work_order.plan_id, simulation_date: date, random_seed: 42 }));
      })
      .catch((cause) => setError(errorMessage(cause)));
  }, [id, initialize]);

  if (!summary || !result) return <div className="portal-page"><Link className="back-link" to={`/supervisor/work-orders/${id}`}><ArrowLeft size={16} /> Verification evidence</Link><div className="empty-card">{error || "Loading the backend simulation result…"}</div></div>;
  const context = result.execution_context;
  const resources = context?.resource_validation;
  const now = Date.parse(result.maintenance.simulated_end || result.maintenance.planned_end);
  return <div className="portal-page">
    <Link className="back-link" to={`/supervisor/work-orders/${id}`}><ArrowLeft size={16} /> Verification evidence</Link>
    <div className="portal-page-heading compact"><div><span className="eyebrow">FINAL DIGITAL TWIN RESULT</span><h1>{result.plan_id} · {result.section_id}</h1><p>Deterministic simulation evidence paired with {summary.work_order.work_order_number}. It is decision support, not live signalling data.</p></div><span className="demo-label">SYNTHETIC DIGITAL TWIN</span></div>
    <div className="supervisor-twin-grid"><section className="twin-stage"><RailwayCorridor assets={assets} selectedId={null} onSelect={selectAsset} simulation={result} now={now} /></section><aside className="twin-command-rail"><section className="twin-side-card"><div className="section-heading"><div><span className="eyebrow">SIMULATION OUTPUT</span><h2>Final KPIs</h2></div><Activity size={18} /></div><dl className="twin-compact-details"><div><dt>Expected delay</dt><dd>{context?.expected_train_delay_min ?? "—"} min</dd></div><div><dt>Simulated delay</dt><dd>{result.kpis.total_delay_min} min</dd></div><div><dt>Maximum delay</dt><dd>{result.kpis.max_single_train_delay_min} min</dd></div><div><dt>Affected trains</dt><dd>{result.kpis.affected_trains_count}</dd></div><div><dt>Simulated duration</dt><dd>{result.maintenance.simulated_duration_min} min</dd></div><div><dt>Safety conflicts</dt><dd>{result.kpis.conflicts_detected}</dd></div></dl></section><section className="twin-side-card"><div className="section-heading"><div><span className="eyebrow">EXECUTION ARRANGEMENT</span><h2>{context?.execution_mode?.replaceAll("_", " ") || "Not linked"}</h2></div><ShieldCheck size={18} /></div><dl className="twin-compact-details"><div><dt>Assigned crew</dt><dd>{context?.assigned_crew_id || "Pending"}</dd></div><div><dt>Manpower</dt><dd>{resources?.manpower_available ? "Available" : "Pending"}</dd></div><div><dt>Equipment</dt><dd>{resources?.equipment_available ? "Available" : "Pending"}</dd></div><div><dt>Materials</dt><dd>{resources?.materials_available ? "Available" : "Pending"}</dd></div></dl><div className={`twin-executable ${context?.executable ? "ready" : "blocked"}`}>{context?.executable ? <CheckCircle2 size={18} /> : <CircleAlert size={18} />}<span><b>{context?.executable ? "Execution ready" : "Execution blocked"}</b><small>{resources?.validation_status || "Backend validation unavailable"}</small></span></div></section></aside></div>
  </div>;
}
