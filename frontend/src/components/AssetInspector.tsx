import { ArrowUpRight, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { Asset } from "../types";
import { titleCase } from "../lib";
import { useAppStore } from "../store/useAppStore";
import RiskBadge from "./RiskBadge";
export default function AssetInspector({ asset }: { asset: Asset }) {
  const navigate = useNavigate(),
    open = useAppStore((s) => s.openSheet);
  return (
    <div className="asset-inspector">
      <div className="section-heading">
        <span className="eyebrow">SELECTED ASSET</span>
        <RiskBadge risk={asset.risk_level} />
      </div>
      <h2>{titleCase(asset.asset_type)}</h2>
      <p className="mono muted">{asset.asset_id}</p>
      <div className="condition-mini">
        <span>Condition</span>
        <b>
          {asset.condition_score}
          <small> / 100</small>
        </b>
      </div>
      <div className="condition-track">
        <span style={{ width: asset.condition_score + "%" }} />
      </div>
      <dl className="details-list">
        <div>
          <dt>Section</dt>
          <dd>{asset.section_id.replace("SEC-", "").replaceAll("-", " → ")}</dd>
        </div>
        <div>
          <dt>Since maintenance</dt>
          <dd>{asset.days_since_maintenance} days</dd>
        </div>
        <div>
          <dt>Previous failures</dt>
          <dd>{asset.previous_failures}</dd>
        </div>
      </dl>
      <button
        className="primary full"
        onClick={() => navigate("/asset/" + asset.asset_id)}
      >
        Inspect asset <ArrowUpRight size={16} />
      </button>
      <button className="secondary full" onClick={open}>
        Plan maintenance <ArrowRight size={15} />
      </button>
    </div>
  );
}
