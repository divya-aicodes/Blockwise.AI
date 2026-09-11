import {
  useMemo,
  useRef,
  useLayoutEffect,
  useState,
  type ComponentRef,
} from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Grid, Html, OrbitControls } from "@react-three/drei";
import { InstancedMesh, Object3D, Vector3 } from "three";
import type { Asset, SimulationResult, MaintenanceRequirement } from "../types";
import {
  sections,
  stations,
  riskColors,
  titleCase,
  trainPosition,
  clock,
} from "../lib";

export interface CorridorProps {
  assets: Asset[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  simulation?: SimulationResult;
  now?: number;
  maintenance?: MaintenanceRequirement | null;
  allAssets?: Asset[];
}
const x = (km: number) => km / 10 - 15.45;
function Sleepers() {
  const ref = useRef<InstancedMesh>(null);
  useLayoutEffect(() => {
    const obj = new Object3D();
    for (let i = 0; i < 160; i++) {
      obj.position.set(-15.6 + i * 0.197, 0.05, 0);
      obj.updateMatrix();
      ref.current!.setMatrixAt(i, obj.matrix);
    }
    ref.current!.instanceMatrix.needsUpdate = true;
  }, []);
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, 160]}>
      <boxGeometry args={[0.08, 0.12, 0.72]} />
      <meshStandardMaterial color="#7aa9a5" />
    </instancedMesh>
  );
}
function AssetMarker({
  asset,
  position,
  selected,
  onSelect,
}: {
  asset: Asset;
  position: [number, number, number];
  selected: boolean;
  onSelect: () => void;
}) {
  const [hover, setHover] = useState(false);
  const color = riskColors[asset.risk_level];
  return (
    <group
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHover(true);
      }}
      onPointerOut={() => setHover(false)}
    >
      <mesh position={[0, 0.08, 0]}>
        <cylinderGeometry
          args={[selected ? 0.27 : 0.16, selected ? 0.27 : 0.16, 0.1, 20]}
        />
        <meshStandardMaterial color={color} />
      </mesh>
      {asset.asset_type === "SIGNAL" ? (
        <group>
          <mesh position={[0, 0.55, 0]}>
            <cylinderGeometry args={[0.035, 0.035, 0.95, 6]} />
            <meshStandardMaterial color="#4c6b78" />
          </mesh>
          <mesh position={[0, 0.94, 0]}>
            <boxGeometry args={[0.17, 0.28, 0.12]} />
            <meshStandardMaterial color={color} />
          </mesh>
        </group>
      ) : asset.asset_type === "OHE" ? (
        <group>
          <mesh position={[0, 0.6, 0]}>
            <boxGeometry args={[0.06, 1.2, 0.06]} />
            <meshStandardMaterial color="#4c6b78" />
          </mesh>
          <mesh position={[0, 1.2, -0.25]}>
            <boxGeometry args={[0.08, 0.05, 0.6]} />
            <meshStandardMaterial color="#4c6b78" />
          </mesh>
        </group>
      ) : (
        <mesh position={[0, 0.26, 0]}>
          <boxGeometry args={[0.18, 0.32, 0.21]} />
          <meshStandardMaterial color={selected ? "#ffffff" : "#527c82"} />
        </mesh>
      )}
      {selected && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
          <ringGeometry args={[0.32, 0.36, 32]} />
          <meshBasicMaterial color="#2f806d" />
        </mesh>
      )}
      {(hover || selected) && (
        <Html position={[0, 1.55, 0]} center zIndexRange={[5, 0]}>
          <div className="scene-tooltip">
            <b>{asset.asset_id}</b>
            <span>
              {titleCase(asset.asset_type)} · {asset.condition_score}/100
            </span>
            <span>
              {asset.risk_level} · {asset.section_id}
            </span>
          </div>
        </Html>
      )}
    </group>
  );
}
function Scene(props: CorridorProps) {
  const { assets, selectedId, onSelect, simulation, now, maintenance } = props;
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const all = props.allAssets || assets;
  const positions = useMemo(
    () =>
      Object.fromEntries(
        all.map((asset) => {
          const section = sections.find((s) => s.id === asset.section_id)!;
          const peers = all.filter((a) => a.section_id === asset.section_id);
          const i = peers.findIndex((a) => a.asset_id === asset.asset_id);
          return [
            asset.asset_id,
            [
              x(
                section.start +
                  (section.distance * (i + 1)) / (peers.length + 1),
              ),
              0,
              (i % 2 === 0 ? 1 : -1) * 1.05,
            ] as [number, number, number],
          ];
        }),
      ),
    [all],
  );
  const target = useMemo(
    () =>
      new Vector3(
        selectedId && positions[selectedId]
          ? positions[selectedId][0] * 0.45
          : 0,
        0,
        0,
      ),
    [selectedId, positions],
  );
  const changed = useRef(false);
  useLayoutEffect(() => {
    changed.current = true;
  }, [target]);
  useFrame((state) => {
    if (changed.current && controls.current) {
      const distance = controls.current.target.distanceTo(target);
      controls.current.target.lerp(target, 0.09);
      controls.current.update();
      if (distance > 0.01) state.invalidate();
      else changed.current = false;
    }
  });
  const m = simulation?.maintenance;
  const active = !!(
    m &&
    now !== undefined &&
    m.simulated_start &&
    now >= Date.parse(m.simulated_start) &&
    (!m.simulated_end || now < Date.parse(m.simulated_end))
  );
  const closed = active ? simulation?.section_id : undefined;
  return (
    <>
      <color attach="background" args={["#ffffff"]} />
      <ambientLight intensity={1.1} />
      <directionalLight position={[10, 20, 12]} intensity={2} />
      <Grid
        position={[0, -0.13, 0]}
        args={[48, 20]}
        cellSize={1}
        cellThickness={0.5}
        cellColor="#b9d9d4"
        sectionSize={5}
        sectionThickness={0.7}
        sectionColor="#7fb2aa"
        fadeDistance={65}
      />
      <mesh position={[0, -0.06, 0]}>
        <boxGeometry args={[32, 0.15, 1.05]} />
        <meshStandardMaterial color="#b3d3ce" roughness={1} />
      </mesh>
      <Sleepers />
      {[-0.21, 0.21].map((z) => (
        <mesh key={z} position={[0, 0.16, z]}>
          <boxGeometry args={[31.5, 0.08, 0.04]} />
          <meshStandardMaterial
            color="#496d78"
            metalness={0.55}
            roughness={0.4}
          />
        </mesh>
      ))}
      {sections.map((section) => (
        <group key={section.id}>
          {closed === section.id && (
            <group position={[x((section.start + section.end) / 2), 0.32, 0]}>
              <mesh>
                <boxGeometry args={[section.distance / 10, 0.12, 1.4]} />
                <meshStandardMaterial
                  color="#c4811a"
                  transparent
                  opacity={0.45}
                />
              </mesh>
              <Html position={[0, 1.7, 0]} center>
                <span className="maintenance-label">MAINTENANCE ACTIVE</span>
              </Html>
            </group>
          )}
          {!simulation && maintenance?.section_id === section.id && (
            <mesh position={[x((section.start + section.end) / 2), 0.28, 0]}>
              <boxGeometry args={[section.distance / 10, 0.04, 1.3]} />
              <meshStandardMaterial color="#c4811a" transparent opacity={0.3} />
            </mesh>
          )}
          <Html
            position={[x((section.start + section.end) / 2), 0, 2.7]}
            center
            zIndexRange={[2, 0]}
          >
            <div className="section-label">
              <span>{section.id}</span>
              <small>{section.distance} km</small>
            </div>
          </Html>
        </group>
      ))}
      {stations.map((station) => (
        <group key={station.code} position={[x(station.km), 0, 0]}>
          <mesh position={[0, 0.13, -0.85]}>
            <boxGeometry args={[0.95, 0.22, 0.6]} />
            <meshStandardMaterial color="#6e9995" />
          </mesh>
          <mesh position={[0, 0.55, -0.85]}>
            <boxGeometry args={[0.55, 0.7, 0.4]} />
            <meshStandardMaterial color="#8fbeb8" />
          </mesh>
          <mesh position={[0, 0.95, -0.85]}>
            <boxGeometry args={[0.82, 0.08, 0.62]} />
            <meshStandardMaterial color="#ffffff" />
          </mesh>
          <mesh position={[0, 0.25, 0]}>
            <cylinderGeometry args={[0.11, 0.11, 0.12, 16]} />
            <meshStandardMaterial color="#277c75" />
          </mesh>
          <Html position={[0, 1.8, -2.5]} center zIndexRange={[2, 0]}>
            <div className="station-label">
              <small>{station.name}</small>
              <strong>{station.code}</strong>
              <span>{station.km} km</span>
            </div>
          </Html>
        </group>
      ))}
      {assets.map((asset) => (
        <AssetMarker
          key={asset.asset_id}
          asset={asset}
          position={positions[asset.asset_id]}
          selected={selectedId === asset.asset_id}
          onSelect={() => onSelect(asset.asset_id)}
        />
      ))}
      {simulation &&
        now !== undefined &&
        simulation.train_results.map((train, index) => {
          const p = trainPosition(train, now);
          if (!p) return null;
          return (
            <group
              key={train.train_id}
              position={[x(p.km), 0.48, ((index % 3) - 1) * 0.26]}
            >
              <mesh>
                <boxGeometry args={[0.44, 0.25, 0.19]} />
                <meshStandardMaterial
                  color={p.state === "WAITING" ? "#c4811a" : "#277c75"}
                />
              </mesh>
              <Html position={[0, 0.65, 0]} center zIndexRange={[3, 0]}>
                <div
                  className={
                    "train-label " + (p.state === "WAITING" ? "waiting" : "")
                  }
                >
                  {train.train_id}
                  <small>
                    {p.state === "WAITING"
                      ? `Waiting · ${p.waitMinutes} min`
                      : clock(now)}
                  </small>
                </div>
              </Html>
            </group>
          );
        })}
      <OrbitControls
        ref={controls}
        makeDefault
        enablePan={false}
        enableDamping
        minDistance={19}
        maxDistance={45}
        minPolarAngle={0.45}
        maxPolarAngle={1.2}
        minAzimuthAngle={-0.3}
        maxAzimuthAngle={0.3}
      />
    </>
  );
}
export default function ThreeRailwayCorridor(props: CorridorProps) {
  return (
    <Canvas
      camera={{ position: [1, 23, 27], fov: 48, near: 0.1, far: 150 }}
      dpr={[1, 1.5]}
      frameloop="demand"
      gl={{ antialias: true, alpha: false }}
      aria-label="Interactive three-dimensional New Delhi to Jaipur railway schematic"
    >
      <Scene {...props} />
    </Canvas>
  );
}
