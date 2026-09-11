import type { RiskLevel } from "../types";
export default function RiskBadge({ risk }: { risk: RiskLevel }) {
  return (
    <span className={"risk-badge risk-" + risk.toLowerCase()}>
      <span className="status-dot" />
      {risk}
    </span>
  );
}
