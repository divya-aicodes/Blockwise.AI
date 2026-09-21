import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, MapPin, Orbit, ShieldCheck, XCircle } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { workOrdersApi } from "../../api/workOrders";
import { errorMessage } from "../../api/client";
import type { Checklist, ExecutionSummary } from "../../types/api";
import StatusPill from "../../components/StatusPill";

export default function SupervisorWorkOrderPage() {
  const { id = "" } = useParams(); const [summary, setSummary] = useState<ExecutionSummary | null>(null), [lists, setLists] = useState<Checklist[]>([]), [comments, setComments] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  const load = () => Promise.all([workOrdersApi.summary(id), workOrdersApi.checklists(id)]).then(([s,c]) => { setSummary(s); setLists(c); }).catch((e) => setError(errorMessage(e)));
  useEffect(() => { void load(); }, [id]);
  async function verify(approved: boolean) { setBusy(true); setError(null); try { await workOrdersApi.verify(id, approved, comments); await load(); } catch(e) { setError(errorMessage(e)); } finally { setBusy(false); } }
  if (!summary) return <div className="portal-page"><Link className="back-link" to="/supervisor"><ArrowLeft size={16} /> Verification queue</Link><div className="empty-card">{error || "Loading evidence…"}</div></div>;
  const o = summary.work_order;
  return <div className="portal-page"><Link className="back-link" to="/supervisor"><ArrowLeft size={16} /> Verification queue</Link><div className="portal-page-heading compact"><div><span className="eyebrow">INDEPENDENT VERIFICATION</span><h1>{o.work_order_number}</h1><p>{o.title} · {o.section_id}</p></div><StatusPill value={o.status} /></div>{error && <div className="form-error">{error}</div>}
    <section className="comparison-grid"><article><small>PLANNED</small><b>{o.estimated_duration_min ?? "—"} min</b><span>{o.planned_start ? new Date(o.planned_start).toLocaleString("en-IN") : "—"}</span></article><article><small>ACTUAL</small><b>{o.actual_duration_min ?? "—"} min</b><span>{o.actual_start ? new Date(o.actual_start).toLocaleString("en-IN") : "Not recorded"}</span></article><article><small>VARIANCE</small><b>{o.variance_minutes ?? "—"} min</b><span>Overtime {o.overtime_minutes ?? 0} min</span></article><article><small>LOCATION EVIDENCE</small><b><MapPin size={17} /> {o.gps_start && o.gps_end ? "Captured" : "Incomplete"}</b><span>Start and completion coordinates</span></article></section>
    <div className="two-column"><section className="panel-card"><div className="section-heading"><div><h2>Checklist evidence</h2><p>Signed controls from field execution.</p></div><ShieldCheck /></div><div className="evidence-list">{lists.map((l) => <div key={l.id}><span><b>{l.type}</b><small>{Object.keys(l.completed_items).length}/{l.items.length} recorded</small></span>{l.signed_at ? <CheckCircle2 className="success-icon" /> : <XCircle className="danger-icon" />}</div>)}</div><Link className="secondary full" to={`/supervisor/work-orders/${o.id}/digital-twin`}><Orbit size={16} /> View final Digital Twin result</Link></section><section className="panel-card"><span className="eyebrow">SUPERVISOR DECISION</span><h2>Verify outcome</h2><label className="field-label">Comments<textarea value={comments} onChange={(e) => setComments(e.target.value)} placeholder="Record verification evidence or reason for rejection" /></label><div className="verify-actions"><button className="approve" disabled={busy || o.status !== "COMPLETED"} onClick={() => void verify(true)}><CheckCircle2 size={17} /> Approve evidence</button><button className="reject" disabled={busy || o.status !== "COMPLETED" || comments.trim().length < 2} onClick={() => void verify(false)}><XCircle size={17} /> Reject with reason</button></div></section></div>
  </div>;
}
