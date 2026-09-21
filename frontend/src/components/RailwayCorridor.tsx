import { Component, lazy, Suspense, type ReactNode } from "react";
import { useAppStore } from "../store/useAppStore";
import { getCorridorSections } from "../lib";
import type { CorridorProps } from "./ThreeRailwayCorridor";
const ThreeRailwayCorridor = lazy(() => import("./ThreeRailwayCorridor"));
class SceneBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="empty-state">
        <h3>3D viewport unavailable</h3>
        <p>
          Your browser could not initialize WebGL. Asset selection and all
          planning tools remain available below.
        </p>
        <div className="fallback-route">NDLS → RE → AWR → BKI → JP</div>
      </div>
    ) : (
      this.props.children
    );
  }
}
export default function RailwayCorridor(props: CorridorProps) {
  const corridorData = useAppStore((state) => state.corridorData);
  const corridorSections = getCorridorSections(corridorData);
  return (
    <div className="corridor-canvas">
      <div className="canvas-caption">
        <span className="eyebrow">CORRIDOR SCHEMATIC</span>
        <span>Section-level asset placement · not geographic coordinates</span>
      </div>
      <SceneBoundary>
        <Suspense
          fallback={
            <div className="scene-loading">
              <div className="skeleton" />
              Loading railway geometry…
            </div>
          }
        >
          <ThreeRailwayCorridor {...props} />
        </Suspense>
      </SceneBoundary>
      <div className="canvas-legend">
        <span>
          <i style={{ background: "#687f83" }} /> Railway (Multi-track)
        </span>
        <span>
          <i style={{ background: "#e95363" }} /> Critical Asset (High Risk)
        </span>
        <span>
          <i style={{ background: "#e3a54f" }} /> Maintenance
        </span>
        <span className="legend-detail">▮ Signaling Mast</span>
        <span className="legend-detail">⌁ OHE Gantry</span>
        <span className="legend-detail">◇ High Risk Zone</span>
        <span className="legend-detail">▰ Trains</span>
        <span className="legend-detail">⌁ Bridge</span>
        <span className="legend-detail">◉ Tunnel</span>
        <span className="canvas-help">Drag to orbit · Scroll to zoom</span>
      </div>
      <div className="route-ruler" aria-label="Section distances">
        {corridorSections.map((s) => (
          <span key={s.id} style={{ flex: s.distance }}>
            {s.from}—{s.to}
            <small>{s.distance} km</small>
          </span>
        ))}
      </div>
    </div>
  );
}
