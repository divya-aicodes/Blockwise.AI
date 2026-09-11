import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Route,
  ScanLine,
  GitCompareArrows,
  Box,
  Activity,
  ArrowUpRight,
  AlertCircle,
  UsersRound,
} from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import WorkflowProgress from "./WorkflowProgress";
import MaintenanceForm from "./MaintenanceForm";
import DemoGuide from "./DemoGuide";
import { api } from "../api/client";
import { authConfig, tokenKey, type AuthUser } from "../auth";
export default function OperationsShell() {
  const s = useAppStore(),
    location = useLocation();
  const navigate = useNavigate();
  const [hasToken, setHasToken] = useState(() => Boolean(localStorage.getItem(tokenKey)));
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const loadAuth = useCallback(async () => {
    const tokenPresent = Boolean(localStorage.getItem(tokenKey));
    setHasToken(tokenPresent);
    if (!tokenPresent) {
      setAuthUser(null);
      setAuthChecked(true);
      return;
    }
    setAuthChecked(false);
    try {
      const { data } = await api.get<AuthUser>("/auth/me", authConfig());
      setAuthUser(data);
    } catch {
      localStorage.removeItem(tokenKey);
      setAuthUser(null);
      setHasToken(false);
    } finally {
      setAuthChecked(true);
    }
  }, []);
  useEffect(() => {
    void loadAuth();
    const onAuthChanged = () => void loadAuth();
    window.addEventListener("railway-auth-changed", onAuthChanged);
    return () => window.removeEventListener("railway-auth-changed", onAuthChanged);
  }, [loadAuth]);
  const workerRestricted = hasToken && authChecked && authUser?.role !== "ADMIN";
  const accessPending = hasToken && !authChecked;
  const restrictedShell = workerRestricted || accessPending;
  useEffect(() => {
    if (workerRestricted && location.pathname !== "/crew") {
      navigate("/crew", { replace: true });
    }
  }, [location.pathname, navigate, workerRestricted]);
  useEffect(() => {
    if (restrictedShell) return;
    void s.initialize();
    const id = setInterval(() => void s.initialize(), 30000);
    return () => clearInterval(id);
  }, [restrictedShell, s.initialize]);
  const tabs = [
    { to: "/map", label: "Corridor", icon: Route },
    {
      to: s.selectedAssetId ? "/asset/" + s.selectedAssetId : "/asset",
      label: "Asset intelligence",
      icon: ScanLine,
    },
    { to: "/plan", label: "Planning", icon: GitCompareArrows },
    { to: "/twin", label: "Digital twin", icon: Box },
    { to: "/crew", label: "Crew management", icon: UsersRound },
  ].filter((tab) => !restrictedShell || tab.label === "Crew management");
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <header className="command-bar">
        <div className="corridor-brand">
          <span className="rail-logo">
            <Route size={21} />
          </span>
          <strong>
            NDLS <span>→</span> JP
          </strong>
          <span className="corridor-word">CORRIDOR</span>
        </div>
        <div className="command-meta">
          <span className="live-status">
            <span
              className={
                "status-dot " + (s.connected ? "connected" : "disconnected")
              }
            />
            {s.connected ? "Backend connected" : "Backend offline"}
          </span>
          <span className="demo-label">SYNTHETIC DEMO</span>
          <span className="avatar" title="Local demonstration operator">
            OP
          </span>
        </div>
      </header>
      <div className="navigation">
        <nav aria-label="Main navigation">
          {tabs.map((t) => (
            <NavLink
              key={t.label}
              to={t.to}
              className={({ isActive }) =>
                isActive ||
                (t.label === "Asset intelligence" &&
                  location.pathname.startsWith("/asset"))
                  ? "nav-item active"
                  : "nav-item"
              }
            >
              <t.icon size={17} />
              {t.label}
            </NavLink>
          ))}
        </nav>
        {!restrictedShell && <DemoGuide />}
      </div>
      {!restrictedShell && <div className="workflow-bar">
        <WorkflowProgress />
        <span className="context-tag">
          {s.maintenance ? (
            <>
              <span className="status-dot connected" />
              <span className="mono">{s.maintenance.maintenance_id}</span>
              <span>{s.maintenance.section_id}</span>
            </>
          ) : (
            "No maintenance requirement selected"
          )}
        </span>
      </div>}
      {!restrictedShell && s.demo && (
        <div className="guided-tip">
          <Activity size={14} />
          {!s.maintenance
            ? "Guided demo · Inspect the selected asset, calculate risk, then plan maintenance."
            : !s.plans.length
              ? "Guided demo · Detect conflicts, then generate alternatives."
              : !(s.selectedPlanId && s.simulations[s.selectedPlanId])
                ? "Guided demo · Compare plans and simulate your selected alternative."
                : "Guided demo · Explore the playback, review feedback, and record your decision."}
        </div>
      )}
      {!restrictedShell && s.bootError && (
        <div className="connection-error" role="alert">
          <AlertCircle size={16} />
          {s.bootError}
          <button onClick={() => void s.initialize()}>Retry connection</button>
        </div>
      )}
      <main id="main-content">
        <Outlet />
      </main>
      <footer>
        <span>
          NEW DELHI — JAIPUR <span className="footer-divider">/</span> 309 km ·
          4 macro sections
        </span>
        <span>
          Decision support · Human approval required <ArrowUpRight size={12} />
        </span>
      </footer>
      {!restrictedShell && s.sheetOpen && <MaintenanceForm />}
    </div>
  );
}
