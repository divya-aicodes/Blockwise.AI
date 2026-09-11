import { Component, lazy, Suspense, type ReactNode } from "react";
import { sections } from "../lib";
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
          <i style={{ background: "#9ab0bc" }} /> Railway
        </span>
        <span>
          <i style={{ background: "#db6b71" }} /> Critical asset
        </span>
        <span>
          <i style={{ background: "#d6b16b" }} /> Maintenance
        </span>
        <span className="canvas-help">Drag to orbit · Scroll to zoom</span>
      </div>
      <div className="route-ruler" aria-label="Section distances">
        {sections.map((s) => (
          <span key={s.id} style={{ flex: s.distance }}>
            {s.from}—{s.to}
            <small>{s.distance} km</small>
          </span>
        ))}
      </div>
    </div>
  );
}
