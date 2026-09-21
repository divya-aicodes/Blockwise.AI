import { useEffect, useMemo, useState } from "react";
import { Bell, CheckCircle2, Clock3, HardHat } from "lucide-react";
import { notificationsApi } from "../../api/notifications";
import { workOrdersApi } from "../../api/workOrders";
import { errorMessage } from "../../api/client";
import { useAuthStore } from "../../store/useAuthStore";
import type { WorkOrder } from "../../types/api";
import WorkOrderCard from "../../components/WorkOrderCard";

export default function CrewDashboard() {
  const user = useAuthStore((s) => s.user), [orders, setOrders] = useState<WorkOrder[]>([]), [unread, setUnread] = useState(0), [error, setError] = useState<string | null>(null);
  useEffect(() => { Promise.all([workOrdersApi.list(), notificationsApi.list(true)]).then(([o,n]) => { setOrders(o); setUnread(n.length); }).catch((e) => setError(errorMessage(e))); }, []);
  const active = useMemo(() => orders.filter((o) => !["VERIFIED","REJECTED"].includes(o.status)), [orders]);
  return <div className="portal-page"><div className="portal-page-heading"><div><span className="eyebrow">FIELD EXECUTION</span><h1>Your assigned work, {user?.full_name?.split(" ")[0]}.</h1><p>Acknowledge instructions, complete safety checks and record actual field outcomes.</p></div></div>{error && <div className="form-error">{error}</div>}
    <section className="metric-grid crew-metrics"><div><HardHat /><span><small>Active assignments</small><b>{active.length}</b></span></div><div><Bell /><span><small>Unread notifications</small><b>{unread}</b></span></div><div><Clock3 /><span><small>In progress</small><b>{orders.filter((o) => ["IN_PROGRESS","PAUSED"].includes(o.status)).length}</b></span></div><div><CheckCircle2 /><span><small>Completed</small><b>{orders.filter((o) => ["COMPLETED","VERIFIED"].includes(o.status)).length}</b></span></div></section>
    <div className="section-heading"><div><span className="eyebrow">MY QUEUE</span><h2>Next assignments</h2></div></div><div className="work-grid">{active.map((o) => <WorkOrderCard key={o.id} order={o} base="/crew/work-orders" />)}{active.length === 0 && <div className="empty-card">No active work has been assigned to your account.</div>}</div>
  </div>;
}
