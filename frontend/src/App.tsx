import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AdminLayout from "./layouts/AdminLayout";
import CrewLayout from "./layouts/CrewLayout";
import SupervisorLayout from "./layouts/SupervisorLayout";

const LoginPage = lazy(() => import("./pages/auth/LoginPage"));
const RegisterPage = lazy(() => import("./pages/auth/RegisterPage"));
const PendingApprovalPage = lazy(() => import("./pages/auth/PendingApprovalPage"));
const AdminDashboard = lazy(() => import("./pages/admin/AdminDashboard"));
const AdminWorkOrdersPage = lazy(() => import("./pages/admin/AdminWorkOrdersPage"));
const AdminCrewPage = lazy(() => import("./pages/admin/AdminCrewPage"));
const WorkOrderAssignmentPage = lazy(() => import("./pages/admin/WorkOrderAssignmentPage"));
const CrewDashboard = lazy(() => import("./pages/crew/CrewDashboard"));
const CrewWorkOrderPage = lazy(() => import("./pages/crew/CrewWorkOrderPage"));
const SupervisorDashboard = lazy(() => import("./pages/supervisor/SupervisorDashboard"));
const SupervisorWorkOrderPage = lazy(() => import("./pages/supervisor/SupervisorWorkOrderPage"));
const SupervisorTwinPage = lazy(() => import("./pages/supervisor/SupervisorTwinPage"));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage"));
const MapPage = lazy(() => import("./pages/MapPage"));
const AssetPage = lazy(() => import("./pages/AssetPage"));
const PlanPage = lazy(() => import("./pages/PlanPage"));
const TwinPage = lazy(() => import("./pages/TwinPage"));

function RouteLoader() { return <div className="app-loader"><span /><b>Loading operational workspace</b><small>Preparing the selected route…</small></div>; }
function NotFound() { return <div className="portal-page empty-state"><h1>Page not found</h1><a href="/">Return to workspace</a></div>; }

export default function App() {
  return <BrowserRouter><Suspense fallback={<RouteLoader />}><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/pending-approval" element={<PendingApprovalPage />} />

    <Route path="/admin" element={<AdminLayout />}>
      <Route index element={<AdminDashboard />} />
      <Route path="corridor" element={<MapPage />} />
      <Route path="assets/:id" element={<AssetPage />} />
      <Route path="planning/new" element={<PlanPage />} />
      <Route path="planning/:maintenanceId" element={<PlanPage />} />
      <Route path="digital-twin/:planId" element={<TwinPage />} />
      <Route path="work-orders" element={<AdminWorkOrdersPage />} />
      <Route path="work-orders/:id" element={<WorkOrderAssignmentPage />} />
      <Route path="crew" element={<AdminCrewPage />} />
      <Route path="notifications" element={<NotificationsPage />} />
    </Route>

    <Route path="/crew" element={<CrewLayout />}>
      <Route index element={<CrewDashboard />} />
      <Route path="work-orders/:id" element={<CrewWorkOrderPage />} />
      <Route path="notifications" element={<NotificationsPage />} />
    </Route>

    <Route path="/supervisor" element={<SupervisorLayout />}>
      <Route index element={<SupervisorDashboard />} />
      <Route path="work-orders/:id" element={<SupervisorWorkOrderPage />} />
      <Route path="work-orders/:id/digital-twin" element={<SupervisorTwinPage />} />
      <Route path="notifications" element={<NotificationsPage />} />
    </Route>

    <Route path="/map" element={<Navigate to="/admin/corridor" replace />} />
    <Route path="/plan" element={<Navigate to="/admin/planning/new" replace />} />
    <Route path="/twin" element={<Navigate to="/admin" replace />} />
    <Route path="/asset/:id" element={<Navigate to="/admin/corridor" replace />} />
    <Route path="/" element={<Navigate to="/login" replace />} />
    <Route path="*" element={<NotFound />} />
  </Routes></Suspense></BrowserRouter>;
}
