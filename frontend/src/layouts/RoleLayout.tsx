import { useEffect, type ComponentType } from "react";
import {
  Bell,
  Boxes,
  ChevronRight,
  ClipboardCheck,
  LayoutDashboard,
  LogOut,
  Map,
  Orbit,
  ShieldCheck,
  Sparkles,
  Users,
  Wrench,
} from "lucide-react";
import { NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/useAuthStore";
import { useAppStore } from "../store/useAppStore";
import MaintenanceForm from "../components/MaintenanceForm";
import WorkflowProgress from "../components/WorkflowProgress";

export type PortalRole = "ADMIN" | "SUPERVISOR" | "CREW";

type NavItem = {
  to: string;
  label: string;
  description: string;
  icon: ComponentType<{ size?: number }>;
  end?: boolean;
  twin?: boolean;
};

const navigation: Record<PortalRole, NavItem[]> = {
  ADMIN: [
    { to: "/admin", label: "Overview", description: "Operational picture", icon: LayoutDashboard, end: true },
    { to: "/admin/corridor", label: "Corridor", description: "Assets and movement", icon: Map },
    { to: "/admin/planning/new", label: "Planning", description: "Build and simulate", icon: Wrench },
    { to: "/admin/work-orders", label: "Work orders", description: "Assign and control", icon: ClipboardCheck },
    { to: "/admin/crew", label: "Crew", description: "Access and capability", icon: Users },
    { to: "/admin/digital-twin/current", label: "Digital Twin", description: "Scenario playback", icon: Orbit, twin: true },
    { to: "/admin/notifications", label: "Notifications", description: "Targeted updates", icon: Bell },
  ],
  SUPERVISOR: [
    { to: "/supervisor", label: "Review desk", description: "Evidence queue", icon: ShieldCheck, end: true },
    { to: "/supervisor/notifications", label: "Notifications", description: "Verification updates", icon: Bell },
  ],
  CREW: [
    { to: "/crew", label: "My work", description: "Assigned execution", icon: Wrench, end: true },
    { to: "/crew/notifications", label: "Notifications", description: "Targeted updates", icon: Bell },
  ],
};

const roleName = {
  ADMIN: "Admin Operations",
  SUPERVISOR: "Supervisor Review",
  CREW: "Crew Workspace",
};

export default function RoleLayout({ portal }: { portal: PortalRole }) {
  const { user, initializing, loadMe, logout } = useAuthStore();
  const initialize = useAppStore((state) => state.initialize);
  const operationsInitializing = useAppStore((state) => state.initializing);
  const sheetOpen = useAppStore((state) => state.sheetOpen);
  const selectedPlanId = useAppStore((state) => state.selectedPlanId);
  const simulations = useAppStore((state) => state.simulations);
  const location = useLocation();

  useEffect(() => { void loadMe(); }, [loadMe]);
  useEffect(() => { window.scrollTo({ top: 0, left: 0, behavior: "auto" }); }, [location.pathname]);
  useEffect(() => {
    if (portal === "ADMIN" && operationsInitializing) void initialize(true);
  }, [portal, operationsInitializing, initialize]);

  if (initializing) {
    return <div className="app-loader"><span /><b>Opening secure workspace</b><small>Restoring your role and permissions…</small></div>;
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  const allowed = portal === "ADMIN"
    ? user.role === "ADMIN"
    : portal === "SUPERVISOR"
      ? user.role === "SUPERVISOR"
      : !["ADMIN", "SUPERVISOR"].includes(user.role);
  if (!allowed) {
    return <Navigate to={user.role === "ADMIN" ? "/admin" : user.role === "SUPERVISOR" ? "/supervisor" : "/crew"} replace />;
  }

  const home = portal === "ADMIN" ? "/admin" : portal === "SUPERVISOR" ? "/supervisor" : "/crew";
  const currentLabel = [...navigation[portal]]
    .sort((left, right) => right.to.length - left.to.length)
    .find((item) => location.pathname === item.to || (!item.end && location.pathname.startsWith(item.to + "/")))?.label;
  return (
    <div className={`premium-shell portal-${portal.toLowerCase()}`}>
      <aside className="premium-sidebar" aria-label={`${portal.toLowerCase()} navigation`}>
        <NavLink to={home} className="premium-brand">
          <span className="brand-glyph"><Boxes size={21} /></span>
          <span><b>Blockwise<span>.AI</span></b><small>Railway orchestration</small></span>
        </NavLink>

        <div className="role-chip"><Sparkles size={14} /><span><small>ACTIVE WORKSPACE</small><b>{roleName[portal]}</b></span></div>

        <nav>
          {navigation[portal].map((item) => {
            const target = item.twin
              ? selectedPlanId && simulations[selectedPlanId]
                ? `/admin/digital-twin/${selectedPlanId}`
                : "/admin/planning/new"
              : item.to;
            const Icon = item.icon;
            return (
              <NavLink key={item.to} to={target} end={item.end} className={({ isActive }) => isActive ? "active" : ""}>
                <span className="nav-icon"><Icon size={18} /></span>
                <span className="nav-copy"><b>{item.label}</b><small>{item.description}</small></span>
                <ChevronRight className="nav-chevron" size={15} />
              </NavLink>
            );
          })}
        </nav>

        <div className="trust-card"><ShieldCheck size={18} /><span><b>Human-controlled</b><small>Backend safety gates remain authoritative.</small></span></div>
      </aside>

      <header className="premium-header">
        <div><small>{roleName[portal]}</small><b>{location.pathname.includes("digital-twin") ? "Digital Twin" : currentLabel || "Workspace"}</b></div>
        <div className="header-user">
          <span className="user-avatar">{user.full_name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()}</span>
          <span className="user-copy"><b>{user.full_name}</b><small>{user.employee_id} · {user.role}</small></span>
          <button className="icon-button" onClick={logout} title="Sign out" aria-label="Sign out"><LogOut size={17} /></button>
        </div>
      </header>

      <main className="premium-main">
        {portal === "ADMIN" && location.pathname.includes("/planning") && <WorkflowProgress />}
        <Outlet />
      </main>
      {portal === "ADMIN" && sheetOpen && <MaintenanceForm />}
    </div>
  );
}
