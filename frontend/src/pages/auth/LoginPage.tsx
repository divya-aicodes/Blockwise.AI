import { useEffect, useState } from "react";
import { ArrowRight, Box, LockKeyhole, ShieldCheck } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { roleHome, useAuthStore } from "../../store/useAuthStore";

export default function LoginPage() {
  const [employeeId, setEmployeeId] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const { user, initializing, error, login, loadMe } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => { void loadMe(); }, [loadMe]);
  if (!initializing && user) return <Navigate to={roleHome(user.role)} replace />;
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true);
    const next = await login(employeeId, password);
    setBusy(false);
    if (next) navigate((location.state as { from?: string } | null)?.from || roleHome(next.role), { replace: true });
  }
  return (
    <main className="auth-page">
      <section className="auth-story">
        <div className="auth-logo"><Box size={22} /> Blockwise.AI</div>
        <div><span className="eyebrow">INTEGRATED BLOCK PLANNING</span><h1>One operational view.<br />Safer maintenance decisions.</h1><p>Risk, train occupancy, maintenance windows, crew readiness and Digital Twin validation—connected through a human-controlled workflow.</p></div>
        <div className="auth-proof"><ShieldCheck size={21} /><span><b>Safety is a hard constraint</b><small>Recommendations require human approval before execution.</small></span></div>
      </section>
      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit}>
          <LockKeyhole size={28} /><span className="eyebrow">SECURE ACCESS</span><h2>Sign in to operations</h2><p>Use your approved railway employee account.</p>
          <label>Employee ID<input value={employeeId} onChange={(e) => setEmployeeId(e.target.value.toUpperCase())} placeholder="EMP-ADMIN or EMP-001" autoComplete="username" required /></label>
          <label>Password<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="current-password" minLength={12} required /></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="primary auth-submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}<ArrowRight size={17} /></button>
          <p className="auth-link">New crew member? <Link to="/register">Request an account</Link></p>
        </form>
      </section>
    </main>
  );
}
