import { useEffect, useState } from "react";
import { Bell, Check, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { notificationsApi } from "../api/notifications";
import { errorMessage } from "../api/client";
import { useAuthStore } from "../store/useAuthStore";
import type { NotificationRecord } from "../types/api";

export default function NotificationsPage() {
  const user = useAuthStore((s) => s.user), [items, setItems] = useState<NotificationRecord[]>([]), [error, setError] = useState<string | null>(null);
  useEffect(() => { notificationsApi.list().then(setItems).catch((e) => setError(errorMessage(e))); }, []);
  const base = user?.role === "ADMIN" ? "/admin/work-orders" : user?.role === "SUPERVISOR" ? "/supervisor/work-orders" : "/crew/work-orders";
  async function mark(item: NotificationRecord) { try { const updated = await notificationsApi.markRead(item.id); setItems((all) => all.map((x) => x.id === updated.id ? updated : x)); } catch(e) { setError(errorMessage(e)); } }
  return <div className="portal-page"><div className="portal-page-heading"><div><span className="eyebrow">TARGETED COMMUNICATION</span><h1>Notifications</h1><p>Only work-relevant updates routed to the responsible crew, supervisor or provider domain.</p></div></div>{error && <div className="form-error">{error}</div>}
    <section className="notification-list">{items.map((item) => { const wo = item.payload.work_order_id as string | undefined; return <article key={item.id} className={item.read_at ? "" : "unread"}><span className="notification-icon"><Bell size={18} /></span><div><span className="notification-type">{item.type.replaceAll("_", " ")} · {item.priority}</span><h3>{item.title}</h3><p>{item.message}</p><small>{item.created_at ? new Date(item.created_at).toLocaleString("en-IN") : ""}</small></div><div className="notification-actions">{wo && <Link to={`${base}/${wo}`}><ExternalLink size={15} /> Open work</Link>}{!item.read_at && <button onClick={() => void mark(item)}><Check size={15} /> Mark read</button>}</div></article>; })}{items.length === 0 && <div className="empty-card">No notifications yet.</div>}</section>
  </div>;
}
