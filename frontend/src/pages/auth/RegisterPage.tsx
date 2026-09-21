import { useState } from "react";
import { ArrowLeft, ArrowRight, UserPlus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../../api/auth";
import { errorMessage } from "../../api/client";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ employee_id: "", email: "", password: "", full_name: "", role: "GANG", primary_skill: "TRACK", shift_start: "06:00", shift_end: "14:00", affiliation: "DEPARTMENTAL", department_id: "", provider_id: "" });
  const set = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const { affiliation, ...values } = form;
      await authApi.register({
        ...values,
        employee_id: form.employee_id.toUpperCase(),
        department_id: affiliation === "DEPARTMENTAL" ? form.department_id || null : null,
        provider_type: affiliation === "DEPARTMENTAL" ? null : affiliation,
        provider_id: affiliation === "DEPARTMENTAL" ? null : form.provider_id || null,
      });
      navigate("/pending-approval", { state: { employeeId: form.employee_id.toUpperCase() } });
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return (
    <main className="auth-page auth-register"><section className="auth-story"><Link className="back-link" to="/login"><ArrowLeft size={16} /> Back to sign in</Link><div><span className="eyebrow">CREW ONBOARDING</span><h1>Request controlled access.</h1><p>Your account stays inactive until an administrator verifies your railway role and work domain.</p></div></section>
      <section className="auth-panel"><form className="auth-card wide" onSubmit={submit}><UserPlus size={28} /><span className="eyebrow">NEW CREW ACCOUNT</span><h2>Registration details</h2>
        <div className="form-grid"><label>Employee ID<input value={form.employee_id} onChange={(e) => set("employee_id", e.target.value)} placeholder="EMP-001" required /></label><label>Full name<input value={form.full_name} onChange={(e) => set("full_name", e.target.value)} required /></label><label>Email<input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required /></label><label>Password<input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} minLength={12} required /></label><label>Role<select value={form.role} onChange={(e) => set("role", e.target.value)}><option>GANG</option><option>MATE</option><option>GANGMAN</option><option>SUPERVISOR</option></select></label><label>Primary skill<select value={form.primary_skill} onChange={(e) => set("primary_skill", e.target.value)}>{["TRACK","SIGNAL","OHE","POINT_MACHINE","BRIDGE","TELECOM"].map((v) => <option key={v}>{v}</option>)}</select></label><label>Shift start<input type="time" value={form.shift_start} onChange={(e) => set("shift_start", e.target.value)} required /></label><label>Shift end<input type="time" value={form.shift_end} onChange={(e) => set("shift_end", e.target.value)} required /></label><label className="full-field">Work affiliation<select value={form.affiliation} onChange={(e) => { set("affiliation", e.target.value); set("department_id", ""); set("provider_id", ""); }}><option value="DEPARTMENTAL">Departmental</option><option value="AMC_CAMC">AMC / CAMC</option><option value="WORKS_CONTRACT">Works contract</option><option value="OEM_AUTHORIZED">OEM authorized</option></select></label>{form.affiliation === "DEPARTMENTAL" ? <label className="full-field">Department ID<input value={form.department_id} onChange={(e) => set("department_id", e.target.value)} placeholder="e.g. ENG" required /></label> : <label className="full-field">Approved provider reference<input value={form.provider_id} onChange={(e) => set("provider_id", e.target.value)} placeholder={form.affiliation === "AMC_CAMC" ? "e.g. AMC-7" : form.affiliation === "WORKS_CONTRACT" ? "e.g. CONTRACT-12" : "e.g. OEM-SERVICE-4"} required /></label>}</div>
        {error && <div className="form-error" role="alert">{error}</div>}<button className="primary auth-submit" disabled={busy}>{busy ? "Submitting…" : "Submit for approval"}<ArrowRight size={17} /></button>
      </form></section></main>
  );
}
