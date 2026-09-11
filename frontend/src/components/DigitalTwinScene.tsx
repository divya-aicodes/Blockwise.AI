import RailwayCorridor from "./RailwayCorridor";
import { useAppStore } from "../store/useAppStore";
import type { SimulationResult } from "../types";
export default function DigitalTwinScene({
  result,
  now,
}: {
  result: SimulationResult;
  now: number;
}) {
  const s = useAppStore();
  return (
    <RailwayCorridor
      assets={s.assets}
      selectedId={null}
      onSelect={s.selectAsset}
      simulation={result}
      now={now}
    />
  );
}
