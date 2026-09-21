import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Bell, CheckCircle2, ClipboardList, Map, ShieldCheck, Users, Wrench } from "lucide-react";
import { Link } from "react-router-dom";
import { authApi } from "../../api/auth";
import { notificationsApi } from "../../api/notifications";
import { workOrdersApi } from "../../api/workOrders";
import { errorMessage } from "../../api/client";
import { useAppStore } from "../../store/useAppStore";
import type { CrewMember, ExecutionSummary, WorkOrder } from "../../types/api";
import WorkOrderCard from "../../components/WorkOrderCard";

export default function AdminDashboard() {
  const assets = useAppStore((s) => s.assets);
  const health = useAppStore((s) => s.health);
  const plans = useAppStore((s) => s.plans);
  const decisions = useAppStore((s) => s.decisions);
  const simulations = useAppStore((s) => s.simulations);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [summaries, setSummaries] = useState<ExecutionSummary[]>([]);
  const [pending, setPending] = useState<CrewMember[]>([]);
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    Promise.all([workOrdersApi.list(), authApi.pending(), notificationsApi.list(true)])
      .then(async ([o,p,n]) => {
        setOrders(o); setPending(p); setUnread(n.length);
        const authoritative = await Promise.allSettled(o.map((order) => workOrdersApi.summary(order.id)));
        setSummaries(authoritative.flatMap((entry) => entry.status === "fulfilled" ? [entry.value] : []));
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);
  const highRisk = useMemo(() => assets.filter((a) => ["HIGH", "CRITICAL"].includes(a.risk_level)).length, [assets]);
  const blocked = orders.filter((o) => o.status === "DRAFT").length;
  return <div className="portal-page">
    <div className="portal-page-heading"><div><span className="eyebrow">ADMIN OPERATIONS CONSOLE</span><h1>Good operations start with one clear decision.</h1><p>Monitor risk, approve feasible plans, assign accountable teams and track field execution.</p></div><Link className="primary" to="/admin/corridor"><Map size={17} /> Open corridor</Link></div>
    {error && <div className="form-error">{error}</div>}
    <section className="metric-grid">
      <div><Map /><span><small>Corridor assets</small><b>{assets.length}</b></span></div>
      <div><AlertTriangle /><span><small>High-risk assets</small><b>{highRisk}</b></span></div>
      <div><Users /><span><small>Pending accounts</small><b>{pending.length}</b></span></div>
      <div><Wrench /><span><small>Maintenance requirements</small><b>{health?.maintenance_requirements ?? 0}</b></span></div>
      <div><ShieldCheck /><span><small>Plans awaiting approval</small><b>{plans.filter((p) => !decisions[p.plan_id]).length}</b></span></div>
      <div><ClipboardList /><span><small>Awaiting assignment</small><b>{blocked}</b></span></div>
      <div><CheckCircle2 /><span><small>Execution ready</small><b>{summaries.filter((item) => item.execution_status.executable).length}</b></span></div>
      <div><Bell /><span><small>Unread alerts</small><b>{unread}</b></span></div>
      <div><Map /><span><small>Active Digital Twin</small><b>{Object.keys(simulations).length}</b></span></div>
    </section>
    <section className="action-rail"><Link to="/admin/corridor"><span><Map /><b>1. Inspect corridor</b><small>Select an asset and review its risk.</small></span></Link><Link to="/admin/planning/new"><span><Wrench /><b>2. Build a safe plan</b><small>Resolve conflicts and simulate alternatives.</small></span></Link><Link to="/admin/work-orders"><span><ShieldCheck /><b>3. Assign & control</b><small>Select crew; the backend validates eligibility.</small></span></Link></section>
    <div className="section-heading"><div><span className="eyebrow">RECENT EXECUTION</span><h2>Work-order status</h2></div><Link to="/admin/work-orders">View all</Link></div>
    <div className="work-grid">{orders.slice(0, 3).map((o) => <WorkOrderCard key={o.id} order={o} base="/admin/work-orders" />)}{orders.length === 0 && <div className="empty-card">No work orders yet. Approve a simulated plan to create one.</div>}</div>
  </div>;
}
