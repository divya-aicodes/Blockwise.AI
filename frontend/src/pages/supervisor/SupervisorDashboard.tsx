import { useEffect, useState } from "react";
import { CheckCircle2, ClipboardCheck, ShieldAlert } from "lucide-react";
import { workOrdersApi } from "../../api/workOrders";
import { errorMessage } from "../../api/client";
import type { WorkOrder } from "../../types/api";
import WorkOrderCard from "../../components/WorkOrderCard";

export default function SupervisorDashboard() {
  const [orders, setOrders] = useState<WorkOrder[]>([]), [error, setError] = useState<string | null>(null);
  useEffect(() => { workOrdersApi.list().then(setOrders).catch((e) => setError(errorMessage(e))); }, []);
  const review = orders.filter((o) => o.status === "COMPLETED");
  return <div className="portal-page"><div className="portal-page-heading"><div><span className="eyebrow">SUPERVISOR ASSURANCE</span><h1>Verification queue</h1><p>Compare planned work with field evidence before accepting the operational outcome.</p></div></div>{error && <div className="form-error">{error}</div>}
    <section className="metric-grid crew-metrics"><div><ClipboardCheck /><span><small>Awaiting verification</small><b>{review.length}</b></span></div><div><CheckCircle2 /><span><small>Verified</small><b>{orders.filter((o) => o.status === "VERIFIED").length}</b></span></div><div><ShieldAlert /><span><small>Rejected</small><b>{orders.filter((o) => o.status === "REJECTED").length}</b></span></div></section><div className="section-heading"><div><span className="eyebrow">ACTION REQUIRED</span><h2>Completed field work</h2></div></div><div className="work-grid">{review.map((o) => <WorkOrderCard key={o.id} order={o} base="/supervisor/work-orders" />)}{review.length === 0 && <div className="empty-card">No completed work is waiting for verification.</div>}</div>
  </div>;
}
