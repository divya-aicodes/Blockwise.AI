import { ArrowRight, CalendarClock, MapPin } from "lucide-react";
import { Link } from "react-router-dom";
import type { WorkOrder } from "../types/api";
import StatusPill from "./StatusPill";

export default function WorkOrderCard({ order, base }: { order: WorkOrder; base: string }) {
  return <article className="work-card">
    <div className="work-card-top"><span className="mono">{order.work_order_number}</span><StatusPill value={order.status} /></div>
    <h3>{order.title}</h3>
    <div className="work-meta"><span><MapPin size={15} />{order.section_id} · {order.asset_id}</span><span><CalendarClock size={15} />{order.planned_start ? new Date(order.planned_start).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "Not scheduled"}</span></div>
    <div className="work-card-bottom"><span>{order.execution_mode.replaceAll("_", " ")} · {order.required_skill}</span><Link to={`${base}/${order.id}`}>Open <ArrowRight size={15} /></Link></div>
  </article>;
}
