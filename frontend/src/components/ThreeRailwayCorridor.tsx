import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ComponentRef,
  type ReactNode,
} from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Grid, Html, OrbitControls } from "@react-three/drei";
import {
  DoubleSide,
  InstancedMesh,
  Object3D,
  Quaternion,
  Vector3,
} from "three";
import type { Asset, MaintenanceRequirement, SimulationResult } from "../types";
import {
  clock,
  getCorridorSections,
  riskColors,
  stations,
  titleCase,
  trainPosition,
} from "../lib";
import { useAppStore } from "../store/useAppStore";

export interface CorridorProps {
  assets: Asset[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  simulation?: SimulationResult;
  now?: number;
  maintenance?: MaintenanceRequirement | null;
  allAssets?: Asset[];
}

const kmToX = (km: number) => km / 9.75 - 15.85;

function Beam({
  start,
  end,
  width = 0.06,
  color = "#536d78",
}: {
  start: [number, number, number];
  end: [number, number, number];
  width?: number;
  color?: string;
}) {
  const { midpoint, length, quaternion } = useMemo(() => {
    const a = new Vector3(...start);
    const b = new Vector3(...end);
    const direction = b.clone().sub(a);
    return {
      midpoint: a.clone().add(b).multiplyScalar(0.5),
      length: direction.length(),
      quaternion: new Quaternion().setFromUnitVectors(
        new Vector3(0, 1, 0),
        direction.normalize(),
      ),
    };
  }, [start, end]);
  return (
    <mesh position={midpoint} quaternion={quaternion} castShadow>
      <cylinderGeometry args={[width, width, length, 6]} />
      <meshStandardMaterial color={color} metalness={0.45} roughness={0.42} />
    </mesh>
  );
}

function Sleepers() {
  const ref = useRef<InstancedMesh>(null);
  const count = 202;
  useLayoutEffect(() => {
    const object = new Object3D();
    for (let i = 0; i < count; i += 1) {
      object.position.set(-16 + i * 0.16, 0.12, 0);
      object.updateMatrix();
      ref.current?.setMatrixAt(i, object.matrix);
    }
    if (ref.current) ref.current.instanceMatrix.needsUpdate = true;
  }, []);
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, count]} receiveShadow>
      <boxGeometry args={[0.075, 0.09, 1.18]} />
      <meshStandardMaterial color="#81999b" roughness={0.85} />
    </instancedMesh>
  );
}

function TrackBed() {
  return (
    <group>
      <mesh position={[0, -0.01, 0]} receiveShadow>
        <boxGeometry args={[32.6, 0.22, 1.55]} />
        <meshStandardMaterial color="#9daead" roughness={1} />
      </mesh>
      <mesh position={[0, 0.08, 0]} receiveShadow>
        <boxGeometry args={[32.2, 0.08, 1.34]} />
        <meshStandardMaterial color="#667b7d" roughness={1} />
      </mesh>
      <Sleepers />
      {[-0.48, -0.18, 0.18, 0.48].map((z) => (
        <mesh key={z} position={[0, 0.23, z]} castShadow>
          <boxGeometry args={[32.25, 0.075, 0.055]} />
          <meshStandardMaterial color="#41545b" metalness={0.78} roughness={0.25} />
        </mesh>
      ))}
      {[-7.7, -7.15, 0.4, 0.95].map((offset, index) => (
        <group key={offset}>
          <Beam
            start={[offset - 0.75, 0.245, index % 2 ? -0.48 : 0.48]}
            end={[offset + 0.75, 0.245, index % 2 ? 0.48 : -0.48]}
            width={0.035}
            color="#41545b"
          />
        </group>
      ))}
    </group>
  );
}

function Portal({ side, rocky = false }: { side: -1 | 1; rocky?: boolean }) {
  const px = side * 16.1;
  return (
    <group position={[px, 0, 0]} rotation={[0, side === 1 ? Math.PI : 0, 0]}>
      {rocky &&
        [
          [-0.1, 0.2, -1.3, 0.9],
          [0.2, 0.8, -1.55, 1.1],
          [-0.2, 1.25, -1.25, 0.8],
          [0.05, 1.6, -0.8, 0.72],
          [0, 0.25, 1.32, 0.95],
          [0.15, 0.95, 1.42, 1.05],
          [-0.1, 1.5, 1.05, 0.8],
        ].map(([rx, ry, rz, scale], i) => (
          <mesh
            key={i}
            position={[rx, ry, rz]}
            rotation={[i * 0.19, i * 0.33, i * 0.11]}
            scale={scale}
            castShadow
          >
            <dodecahedronGeometry args={[0.85, 0]} />
            <meshStandardMaterial color={i % 2 ? "#59645f" : "#48534f"} roughness={1} />
          </mesh>
        ))}
      {[0, 0.42].map((depth) => (
        <group key={depth} position={[depth, 0, 0]}>
          <mesh position={[0, 0.9, 0]} rotation={[0, Math.PI / 2, 0]} castShadow>
            <torusGeometry args={[1.04, 0.24, 8, 24, Math.PI]} />
            <meshStandardMaterial color="#d9e1df" roughness={0.8} />
          </mesh>
          <mesh position={[0, 0.38, -1.02]} castShadow>
            <boxGeometry args={[0.34, 0.76, 0.28]} />
            <meshStandardMaterial color="#d9e1df" />
          </mesh>
          <mesh position={[0, 0.38, 1.02]} castShadow>
            <boxGeometry args={[0.34, 0.76, 0.28]} />
            <meshStandardMaterial color="#d9e1df" />
          </mesh>
        </group>
      ))}
      {rocky && (
        <mesh position={[0.5, 0.68, 0]} rotation={[0, Math.PI / 2, 0]}>
          <circleGeometry args={[0.78, 24, 0, Math.PI]} />
          <meshStandardMaterial color="#1e3440" side={DoubleSide} />
        </mesh>
      )}
    </group>
  );
}

function Signal({ x, z, red = false }: { x: number; z: number; red?: boolean }) {
  return (
    <group position={[x, 0.2, z]}>
      <mesh position={[0, 0.58, 0]} castShadow>
        <cylinderGeometry args={[0.035, 0.05, 1.15, 7]} />
        <meshStandardMaterial color="#3d5660" metalness={0.5} />
      </mesh>
      <mesh position={[0, 1.17, 0]} castShadow>
        <boxGeometry args={[0.2, 0.38, 0.16]} />
        <meshStandardMaterial color="#283c43" />
      </mesh>
      <mesh position={[0, 1.25, z > 0 ? -0.09 : 0.09]}>
        <sphereGeometry args={[0.055, 12, 12]} />
        <meshStandardMaterial
          color={red ? "#e45863" : "#28a879"}
          emissive={red ? "#e45863" : "#28a879"}
          emissiveIntensity={2}
        />
      </mesh>
    </group>
  );
}

function Gantry({ x }: { x: number }) {
  return (
    <group position={[x, 0.2, 0]}>
      {[-0.9, 0.9].map((z) => (
        <mesh key={z} position={[0, 0.75, z]} castShadow>
          <boxGeometry args={[0.055, 1.55, 0.055]} />
          <meshStandardMaterial color="#61767d" metalness={0.6} />
        </mesh>
      ))}
      <mesh position={[0, 1.48, 0]} castShadow>
        <boxGeometry args={[0.07, 0.07, 1.85]} />
        <meshStandardMaterial color="#61767d" metalness={0.6} />
      </mesh>
      <Beam start={[-0.01, 0.3, -0.9]} end={[-0.01, 1.48, 0.9]} width={0.022} />
      <Beam start={[-0.01, 1.48, -0.9]} end={[-0.01, 0.3, 0.9]} width={0.022} />
    </group>
  );
}

function TelecomTower() {
  return (
    <group position={[-9.5, 0.15, -2.1]}>
      {[[-0.35, 0, -0.25], [0.35, 0, -0.25], [0, 0, 0.3]].map((p, i) => (
        <Beam key={i} start={p as [number, number, number]} end={[0, 3.15, 0]} width={0.035} color="#66767c" />
      ))}
      {[0.75, 1.45, 2.15].map((y) => (
        <group key={y}>
          <Beam start={[-0.26, y, -0.18]} end={[0.26, y, -0.18]} width={0.024} />
          <Beam start={[-0.24, y, -0.16]} end={[0, y, 0.22]} width={0.024} />
          <Beam start={[0.24, y, -0.16]} end={[0, y, 0.22]} width={0.024} />
        </group>
      ))}
      {[-0.34, 0.34].map((xOffset) => (
        <mesh key={xOffset} position={[xOffset, 2.45, 0]} rotation={[0, 0, 0.35 * Math.sign(xOffset)]}>
          <sphereGeometry args={[0.16, 12, 8, 0, Math.PI]} />
          <meshStandardMaterial color="#dde5e3" />
        </mesh>
      ))}
    </group>
  );
}

function Hut({ x, z, label }: { x: number; z: number; label: string }) {
  return (
    <group position={[x, 0.18, z]}>
      <mesh position={[0, 0.35, 0]} castShadow>
        <boxGeometry args={[0.72, 0.68, 0.58]} />
        <meshStandardMaterial color="#d8e5e1" />
      </mesh>
      <mesh position={[0, 0.75, 0]} rotation={[0, 0, Math.PI / 4]} castShadow>
        <boxGeometry args={[0.52, 0.52, 0.69]} />
        <meshStandardMaterial color="#a5b5b3" />
      </mesh>
      <Html position={[0, 0.55, z > 0 ? 0.31 : -0.31]} center transform distanceFactor={8}>
        <span className="trackside-label">{label}</span>
      </Html>
    </group>
  );
}

function DottedZone({ x, z, sx, sz }: { x: number; z: number; sx: number; sz: number }) {
  const dots = 30;
  const positions = Array.from({ length: dots }, (_, index) => {
    const t = index / dots;
    const angle = t * Math.PI * 2;
    return [x + Math.cos(angle) * sx, 0.22, z + Math.sin(angle) * sz] as const;
  });
  return (
    <group>
      {positions.map((p, index) => (
        <mesh key={index} position={p}>
          <sphereGeometry args={[0.045, 7, 7]} />
          <meshStandardMaterial color="#ee756f" emissive="#e45d60" emissiveIntensity={0.8} />
        </mesh>
      ))}
    </group>
  );
}

function Terrain() {
  return (
    <group>
      <group position={[-7.7, -0.14, 1.7]}>
        <mesh rotation={[0.05, 0.05, 0.02]} castShadow receiveShadow>
          <boxGeometry args={[5.1, 0.78, 3.25]} />
          <meshStandardMaterial color="#786e5e" roughness={1} />
        </mesh>
        {[[-1.8, 0.55, 1.2], [-0.9, 0.66, 1.3], [0.2, 0.55, 1.35], [1.3, 0.62, 1.15]].map((p, i) => (
          <mesh key={i} position={p as [number, number, number]} rotation={[i * 0.25, 0, i * 0.18]}>
            <dodecahedronGeometry args={[0.42, 0]} />
            <meshStandardMaterial color={i % 2 ? "#666153" : "#8b7c68"} />
          </mesh>
        ))}
        <DottedZone x={0} z={0.2} sx={2.2} sz={1.26} />
        <Html position={[-0.1, 1.42, 1]} center>
          <div className="zone-label">High Risk Zone:<b>Curves (88–92km)</b></div>
        </Html>
      </group>
      <group position={[8.6, -0.22, 1.35]}>
        <mesh receiveShadow castShadow rotation={[0.03, -0.06, 0]}>
          <boxGeometry args={[5.5, 0.85, 3.7]} />
          <meshStandardMaterial color="#6e7163" roughness={1} />
        </mesh>
        <mesh position={[0.7, 0.47, 0.45]} rotation={[-Math.PI / 2, 0, 0.25]}>
          <planeGeometry args={[5.9, 0.85]} />
          <meshStandardMaterial color="#74a8b1" roughness={0.35} />
        </mesh>
      </group>
    </group>
  );
}

function AlertMarker({
  x,
  z,
  title,
  detail,
  maintenance = false,
}: {
  x: number;
  z: number;
  title: string;
  detail: string;
  maintenance?: boolean;
}) {
  const color = maintenance ? "#e3a54f" : "#e95363";
  return (
    <group position={[x, 0.2, z]}>
      <pointLight color={color} intensity={2.4} distance={3.2} />
      <mesh position={[0, 0.75, 0]} rotation={[0.4, 0.55, 0.2]} castShadow>
        <octahedronGeometry args={[0.28, 0]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1.5} />
      </mesh>
      <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.5, 0.56, 32]} />
        <meshBasicMaterial color={color} transparent opacity={0.75} />
      </mesh>
      <Html position={[0, 1.55, 0]} center>
        <div className={`corridor-alert${maintenance ? " maintenance" : ""}`}>
          <span>{title}</span><b>{detail}</b>
        </div>
      </Html>
    </group>
  );
}

function RoadCrossing() {
  return (
    <group position={[0.6, 0.16, 0]}>
      <mesh position={[0, 0.02, 0]} receiveShadow>
        <boxGeometry args={[1.2, 0.08, 4.5]} />
        <meshStandardMaterial color="#556369" roughness={0.95} />
      </mesh>
      {[-0.22, 0.22].map((lane) => (
        <mesh key={lane} position={[lane, 0.075, 0]}>
          <boxGeometry args={[0.025, 0.01, 4.3]} />
          <meshStandardMaterial color="#ecdda7" />
        </mesh>
      ))}
      {[-1.25, 1.25].map((z, index) => (
        <group key={z} position={[0.63 * (index ? -1 : 1), 0, z]}>
          <mesh position={[0, 0.45, 0]}>
            <cylinderGeometry args={[0.04, 0.05, 0.9, 8]} />
            <meshStandardMaterial color="#d7e0df" />
          </mesh>
          <mesh position={[0.43 * (index ? -1 : 1), 0.82, 0]} rotation={[0, 0, index ? -0.28 : 0.28]}>
            <boxGeometry args={[0.9, 0.07, 0.07]} />
            <meshStandardMaterial color="#e15f61" />
          </mesh>
        </group>
      ))}
      <group position={[-0.32, 0.18, 1.85]}>
        <mesh position={[0, 0.2, 0]} castShadow>
          <boxGeometry args={[0.42, 0.34, 0.7]} />
          <meshStandardMaterial color="#d6a648" />
        </mesh>
        <mesh position={[0, 0.28, -0.47]} castShadow>
          <boxGeometry args={[0.4, 0.42, 0.26]} />
          <meshStandardMaterial color="#f0ca67" />
        </mesh>
      </group>
    </group>
  );
}

function TrussBridge() {
  const bx = 8.7;
  return (
    <group position={[bx, 0.23, 0]}>
      {[-0.92, 0.92].map((z) => (
        <group key={z} position={[0, 0, z]}>
          <Beam start={[-1.65, 0.1, 0]} end={[-1.65, 1.15, 0]} width={0.045} />
          <Beam start={[1.65, 0.1, 0]} end={[1.65, 1.15, 0]} width={0.045} />
          <Beam start={[-1.65, 1.15, 0]} end={[1.65, 1.15, 0]} width={0.045} />
          {[-1.1, -0.55, 0, 0.55, 1.1].map((sx, i) => (
            <group key={sx}>
              <Beam start={[sx, 0.1, 0]} end={[sx, 1.15, 0]} width={0.035} />
              <Beam start={[sx, 0.1, 0]} end={[sx + (i % 2 ? -0.55 : 0.55), 1.15, 0]} width={0.027} />
            </group>
          ))}
        </group>
      ))}
      {[-1.25, -0.42, 0.42, 1.25].map((sx) => (
        <Beam key={sx} start={[sx, 1.35, -0.92]} end={[sx, 1.35, 0.92]} width={0.035} />
      ))}
    </group>
  );
}

function StaticTrain({ x, z, freight = false }: { x: number; z: number; freight?: boolean }) {
  const colors = freight ? ["#ce6d56", "#4d91ae", "#d6a54e"] : ["#f4f5ef", "#f4f5ef", "#f4f5ef"];
  return (
    <group position={[x, 0.51, z]}>
      {colors.map((color, index) => (
        <group key={index} position={[(index - 1) * 0.84, 0, 0]}>
          <mesh castShadow>
            <boxGeometry args={[0.74, freight ? 0.45 : 0.38, 0.32]} />
            <meshStandardMaterial color={color} metalness={0.2} roughness={0.5} />
          </mesh>
          {!freight && (
            <mesh position={[0, 0.04, z > 0 ? -0.171 : 0.171]}>
              <boxGeometry args={[0.5, 0.1, 0.018]} />
              <meshStandardMaterial color="#276a7b" emissive="#265b67" emissiveIntensity={0.25} />
            </mesh>
          )}
          {[-0.24, 0.24].map((wheelX) => (
            <mesh key={wheelX} position={[wheelX, -0.24, 0]} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.08, 0.08, 0.35, 12]} />
              <meshStandardMaterial color="#26363c" />
            </mesh>
          ))}
        </group>
      ))}
      {!freight && (
        <mesh position={[1.32, 0, 0]} rotation={[0, 0, -Math.PI / 2]} castShadow>
          <coneGeometry args={[0.2, 0.38, 4]} />
          <meshStandardMaterial color="#f4f5ef" />
        </mesh>
      )}
    </group>
  );
}

function Station({ code, name, km }: { code: string; name: string; km: number }) {
  const sx = kmToX(km);
  const compact = code === "RE" || code === "AWR";
  return (
    <group position={[sx, 0.18, -1.05]}>
      <mesh position={[0, 0.12, 0]} receiveShadow>
        <boxGeometry args={[compact ? 1 : 1.35, 0.22, 0.72]} />
        <meshStandardMaterial color="#cbdad7" />
      </mesh>
      <mesh position={[0, 0.55, 0]} castShadow>
        <boxGeometry args={[compact ? 0.55 : 0.82, 0.64, 0.5]} />
        <meshStandardMaterial color="#a3c5bd" />
      </mesh>
      <mesh position={[0, 0.91, 0]} castShadow>
        <boxGeometry args={[compact ? 0.78 : 1.05, 0.1, 0.7]} />
        <meshStandardMaterial color="#f0f3f1" />
      </mesh>
      <Html position={[0, 1.75, -0.25]} center>
        <div className="station-label">
          <small>{name}</small><strong>{code}</strong><span>{km} km</span>
        </div>
      </Html>
    </group>
  );
}

function Telemetry({ x, z, label }: { x: number; z: number; label: string }) {
  return (
    <Html position={[x, 2.75, z]} center distanceFactor={9}>
      <div className="telemetry-card">
        <span>{label} · NORMAL</span>
        <svg viewBox="0 0 120 28" aria-hidden="true">
          <polyline points="0,19 12,17 23,20 36,16 48,18 60,9 72,13 83,7 96,10 108,5 120,8" />
        </svg>
      </div>
    </Html>
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
  const marker: ReactNode = asset.asset_type === "SIGNAL" ? (
    <Signal x={0} z={0} red={asset.risk_level === "CRITICAL"} />
  ) : asset.asset_type === "OHE" ? (
    <Gantry x={0} />
  ) : (
    <group>
      <mesh position={[0, 0.34, 0]} castShadow>
        <cylinderGeometry args={[0.1, 0.15, 0.5, 8]} />
        <meshStandardMaterial color={color} />
      </mesh>
      <mesh position={[0, 0.68, 0]} castShadow>
        <boxGeometry args={[0.22, 0.25, 0.22]} />
        <meshStandardMaterial color="#426d6d" />
      </mesh>
    </group>
  );
  return (
    <group
      position={position}
      onClick={(event) => {
        event.stopPropagation();
        onSelect();
      }}
      onPointerOver={(event) => {
        event.stopPropagation();
        setHover(true);
      }}
      onPointerOut={() => setHover(false)}
    >
      {marker}
      <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[selected ? 0.28 : 0.16, selected ? 0.35 : 0.2, 24]} />
        <meshBasicMaterial color={selected ? "#2f806d" : color} transparent opacity={0.9} />
      </mesh>
      {(hover || selected) && (
        <Html position={[0, 1.55, 0]} center zIndexRange={[12, 0]}>
          <div className="scene-tooltip">
            <b>{asset.asset_id}</b>
            <span>{titleCase(asset.asset_type)} · {asset.condition_score}/100</span>
            <span>{asset.risk_level} · {asset.section_id}</span>
          </div>
        </Html>
      )}
    </group>
  );
}

function Scene(props: CorridorProps) {
  const { assets, selectedId, onSelect, simulation, now, maintenance } = props;
  const corridorData = useAppStore((state) => state.corridorData);
  const activeSections = useMemo(() => getCorridorSections(corridorData), [corridorData]);
  const sourceStations = useMemo(
    () => (corridorData?.stations?.length ? corridorData.stations : stations),
    [corridorData],
  );
  const activeStations = useMemo(
    () =>
      sourceStations.map((station) => ({
        ...station,
        km:
          Number(station.km) ||
          stations.find((fallback) => fallback.code === station.code)?.km ||
          0,
      })),
    [sourceStations],
  );
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const all = props.allAssets || assets;
  const positions = useMemo(
    () =>
      Object.fromEntries(
        all.map((asset) => {
          const section = activeSections.find((candidate) => candidate.id === asset.section_id) || activeSections[0];
          const peers = all.filter((candidate) => candidate.section_id === asset.section_id);
          const index = peers.findIndex((candidate) => candidate.asset_id === asset.asset_id);
          return [
            asset.asset_id,
            [
              kmToX((section?.start ?? 0) + ((section?.distance ?? 50) * (index + 1)) / (peers.length + 1)),
              0.22,
              (index % 2 === 0 ? 1 : -1) * 1.14,
            ] as [number, number, number],
          ];
        }),
      ),
    [all, activeSections],
  );
  const target = useMemo(
    () => new Vector3(selectedId && positions[selectedId] ? positions[selectedId][0] * 0.25 : 0, 0.2, 0),
    [selectedId, positions],
  );
  const moving = useRef(false);
  useLayoutEffect(() => {
    moving.current = true;
  }, [target]);
  useFrame((state) => {
    if (!moving.current || !controls.current) return;
    const distance = controls.current.target.distanceTo(target);
    controls.current.target.lerp(target, 0.075);
    controls.current.update();
    if (distance > 0.01) state.invalidate();
    else moving.current = false;
  });

  const simulatedMaintenance = simulation?.maintenance;
  const maintenanceActive = Boolean(
    simulatedMaintenance &&
      now !== undefined &&
      simulatedMaintenance.simulated_start &&
      now >= Date.parse(simulatedMaintenance.simulated_start) &&
      (!simulatedMaintenance.simulated_end || now < Date.parse(simulatedMaintenance.simulated_end)),
  );
  const closedSection = maintenanceActive ? simulation?.section_id : undefined;

  return (
    <>
      <color attach="background" args={["#faf7f8"]} />
      <fog attach="fog" args={["#faf7f8", 36, 68]} />
      <ambientLight intensity={0.72} />
      <hemisphereLight args={["#ffffff", "#afc4bd", 0.62]} />
      <directionalLight
        position={[10, 18, 10]}
        intensity={1.25}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-22}
        shadow-camera-right={22}
        shadow-camera-top={12}
        shadow-camera-bottom={-12}
      />
      <Grid
        position={[0, -0.19, 0]}
        args={[49, 22]}
        cellSize={0.72}
        cellThickness={0.5}
        cellColor="#eadfe5"
        sectionSize={3.6}
        sectionThickness={0.85}
        sectionColor="#d8cce5"
        fadeDistance={52}
        fadeStrength={1.4}
      />
      <Terrain />
      <TrackBed />
      <Portal side={-1} />
      <Portal side={1} rocky />
      <TelecomTower />
      <RoadCrossing />
      <TrussBridge />
      {[-12.5, -5.2, 3.4, 12.1].map((gantryX) => <Gantry key={gantryX} x={gantryX} />)}
      {[-13.3, -10.4, -6.2, -2.7, 2.3, 5.9, 11.6, 14.3].map((signalX, index) => (
        <Signal key={signalX} x={signalX} z={index % 2 ? -1.12 : 1.12} red={index === 3 || index === 5} />
      ))}
      <Hut x={-11.1} z={-1.85} label="RELAY" />
      <Hut x={-3.1} z={-1.75} label="AUTO" />
      <Hut x={4.5} z={-1.65} label="PANEL" />
      <AlertMarker x={-5.2} z={-1.12} title="HIGH RISK" detail="TRACK WARP (114km)" />
      <AlertMarker x={-2.15} z={1.2} title="MAINTENANCE" detail="POINTS (145km)" maintenance />
      <AlertMarker x={8.25} z={-1.05} title="CRITICAL ASSET" detail="BRIDGE (191km)" />
      <DottedZone x={4.9} z={0} sx={2.2} sz={1.25} />
      <Html position={[4.9, 0.65, 2.05]} center>
        <div className="zone-label">High Risk Zone:<b>Junction approach</b></div>
      </Html>
      <StaticTrain x={4.2} z={-0.33} />
      <StaticTrain x={9.5} z={0.33} freight />
      <Telemetry x={1.9} z={-1.9} label="TELEMETRY T8" />
      <Telemetry x={7.1} z={-1.9} label="TELEMETRY T6" />

      {activeSections.map((section) => (
        <group key={section.id}>
          {(closedSection === section.id || (!simulation && maintenance?.section_id === section.id)) && (
            <mesh position={[kmToX((section.start + section.end) / 2), 0.3, 0]}>
              <boxGeometry args={[section.distance / 9.75, 0.08, 1.56]} />
              <meshStandardMaterial color="#d89d45" transparent opacity={closedSection ? 0.42 : 0.24} />
            </mesh>
          )}
          <Html position={[kmToX((section.start + section.end) / 2), 0.25, 2.75]} center zIndexRange={[3, 0]}>
            <div className="section-label"><span>{section.id}</span><small>{section.distance} km</small></div>
          </Html>
        </group>
      ))}
      {activeStations.map((station) => (
        <Station key={station.code} code={station.code} name={station.name} km={station.km} />
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
      {simulation && now !== undefined && simulation.train_results.map((train, index) => {
        const current = trainPosition(train, now);
        if (!current) return null;
        return (
          <group key={train.train_id} position={[kmToX(current.km), 0.58, index % 2 ? 0.34 : -0.34]}>
            <mesh castShadow>
              <boxGeometry args={[0.52, 0.27, 0.22]} />
              <meshStandardMaterial color={current.state === "WAITING" ? "#d1933b" : "#287d72"} />
            </mesh>
            <Html position={[0, 0.62, 0]} center zIndexRange={[8, 0]}>
              <div className={`train-label ${current.state === "WAITING" ? "waiting" : ""}`}>
                {train.train_id}
                <small>{current.state === "WAITING" ? `Waiting · ${current.waitMinutes} min` : clock(now)}</small>
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
        dampingFactor={0.07}
        minDistance={19}
        maxDistance={44}
        minPolarAngle={0.54}
        maxPolarAngle={Math.PI / 2.2}
        minAzimuthAngle={-0.42}
        maxAzimuthAngle={0.42}
      />
    </>
  );
}

export default function ThreeRailwayCorridor(props: CorridorProps) {
  return (
    <Canvas
      shadows
      camera={{ position: [0, 18.5, 25.5], fov: 47, near: 0.1, far: 150 }}
      dpr={[1, 1.5]}
      frameloop="demand"
      gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
      aria-label="Interactive three-dimensional New Delhi to Jaipur railway operations corridor"
    >
      <Scene {...props} />
    </Canvas>
  );
}
