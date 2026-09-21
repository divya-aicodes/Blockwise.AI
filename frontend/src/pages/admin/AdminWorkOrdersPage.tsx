import { useEffect, useMemo, useState } from "react";
import { ClipboardList, Search } from "lucide-react";
import { workOrdersApi } from "../../api/workOrders";
import { errorMessage } from "../../api/client";
import type { WorkOrder } from "../../types/api";
import WorkOrderCard from "../../components/WorkOrderCard";

export default function AdminWorkOrdersPage() {
  const [orders, setOrders] = useState<WorkOrder[]>([]), [filter, setFilter] = useState("ALL"), [query, setQuery] = useState(""), [error, setError] = useState<string | null>(null);
  useEffect(() => { workOrdersApi.list().then(setOrders).catch((e) => setError(errorMessage(e))); }, []);
  const visible = useMemo(() => orders.filter((o) => (filter === "ALL" || o.status === filter) && `${o.work_order_number} ${o.asset_id} ${o.section_id}`.toLowerCase().includes(query.toLowerCase())), [orders, filter, query]);
  return <div className="portal-page"><div className="portal-page-heading"><div><span className="eyebrow">EXECUTION CONTROL</span><h1>Work orders</h1><p>Approved plans become controlled, traceable field work here.</p></div></div>
    <div className="filter-bar"><label className="search-field"><Search size={16} /><input placeholder="Search work order, asset or section" value={query} onChange={(e) => setQuery(e.target.value)} /></label><select value={filter} onChange={(e) => setFilter(e.target.value)}>{["ALL","DRAFT","ASSIGNED","ACKNOWLEDGED","IN_PROGRESS","PAUSED","COMPLETED","VERIFIED","REJECTED"].map((v) => <option key={v}>{v}</option>)}</select></div>
    {error && <div className="form-error">{error}</div>}<div className="work-grid">{visible.map((o) => <WorkOrderCard key={o.id} order={o} base="/admin/work-orders" />)}{visible.length === 0 && <div className="empty-card"><ClipboardList size={28} /><b>No matching work orders</b><span>Approve a safe simulated plan or change the current filter.</span></div>}</div>
  </div>;
}
