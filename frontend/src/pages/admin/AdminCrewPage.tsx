import { useEffect, useState } from "react";
import { Check, ShieldCheck, Users } from "lucide-react";
import { authApi } from "../../api/auth";
import { errorMessage } from "../../api/client";
import type { CrewMember } from "../../types/api";

const affiliation = (crew: CrewMember) => crew.provider_type
  ? `${crew.provider_type.replaceAll("_", " ")} · ${crew.provider_id || "reference pending"}`
  : `Department · ${crew.department_id || "not recorded"}`;

export default function AdminCrewPage() {
  const [pending, setPending] = useState<CrewMember[]>([]), [active, setActive] = useState<CrewMember[]>([]), [error, setError] = useState<string | null>(null), [busy, setBusy] = useState<string | null>(null);
  const load = () => Promise.all([authApi.pending(), authApi.active()]).then(([p,a]) => { setPending(p); setActive(a); }).catch((e) => setError(errorMessage(e)));
  useEffect(() => { void load(); }, []);
  async function approve(id: string) { setBusy(id); setError(null); try { await authApi.approve(id); await load(); } catch(e) { setError(errorMessage(e)); } finally { setBusy(null); } }
  return <div className="portal-page"><div className="portal-page-heading"><div><span className="eyebrow">ACCESS & CAPABILITY</span><h1>Crew management</h1><p>Approve identities, then assign work only to active people with matching skills and affiliation.</p></div></div>{error && <div className="form-error">{error}</div>}
    <div className="two-column"><section className="panel-card"><div className="section-heading"><div><h2>Pending approval</h2><p>{pending.length} account request(s)</p></div><ShieldCheck /></div><div className="people-list">{pending.map((c) => <article key={c.employee_id}><span className="avatar">{c.full_name.slice(0,2).toUpperCase()}</span><span><b>{c.full_name}</b><small>{c.employee_id} · {c.role} · {c.primary_skill}</small><small>{affiliation(c)}</small></span><button className="small-button" disabled={busy === c.employee_id} onClick={() => void approve(c.employee_id)}><Check size={15} /> Approve</button></article>)}{pending.length === 0 && <div className="empty-inline">No pending accounts.</div>}</div></section>
      <section className="panel-card"><div className="section-heading"><div><h2>Active workforce</h2><p>{active.length} approved member(s)</p></div><Users /></div><div className="people-list">{active.map((c) => <article key={c.employee_id}><span className="avatar">{c.full_name.slice(0,2).toUpperCase()}</span><span><b>{c.full_name}</b><small>{c.employee_id} · {c.role} · {c.primary_skill} · {c.availability}</small><small>{affiliation(c)}</small></span></article>)}</div></section></div>
  </div>;
}
