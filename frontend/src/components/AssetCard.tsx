import type { Asset } from "../types";
import { titleCase } from "../lib";
import RiskBadge from "./RiskBadge";
export default function AssetCard({
  asset,
  selected,
  onSelect,
}: {
  asset: Asset;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      className={"asset-row " + (selected ? "selected" : "")}
      onClick={onSelect}
    >
      <span>
        <b className="mono">{asset.asset_id}</b>
        <small>
          {titleCase(asset.asset_type)} ·{" "}
          {asset.section_id.replace("SEC-", "").replaceAll("-", " → ")}
        </small>
      </span>
      <RiskBadge risk={asset.risk_level} />
    </button>
  );
}
