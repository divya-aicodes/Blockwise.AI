import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import OperationsShell from "./components/OperationsShell";
import MapPage from "./pages/MapPage";
import AssetPage from "./pages/AssetPage";
import PlanPage from "./pages/PlanPage";
import TwinPage from "./pages/TwinPage";
import CrewPage from "./pages/CrewPage";
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<OperationsShell />}>
          <Route index element={<Navigate to="/map" replace />} />
          <Route path="map" element={<MapPage />} />
          <Route path="asset" element={<AssetPage />} />
          <Route path="asset/:id" element={<AssetPage />} />
          <Route path="plan" element={<PlanPage />} />
          <Route path="twin" element={<TwinPage />} />
          <Route path="crew" element={<CrewPage />} />
          <Route
            path="*"
            element={
              <div className="page empty-state">
                <h1>Page not found</h1>
                <a href="/map">Return to corridor</a>
              </div>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
