import { Check, ChevronRight } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
export default function WorkflowProgress() {
  const s = useAppStore();
  const done = [
    !!s.selectedAssetId,
    !!(s.selectedAssetId && s.risks[s.selectedAssetId]),
    !!s.maintenance,
    !!s.conflicts,
    s.plans.length > 0,
    !!(s.selectedPlanId && s.simulations[s.selectedPlanId]),
    !!(s.selectedPlanId && s.decisions[s.selectedPlanId]),
  ];
  return (
    <div className="workflow" aria-label="Planning workflow">
      {[
        "Asset",
        "Risk",
        "Maintenance",
        "Conflicts",
        "Alternatives",
        "Simulation",
        "Decision",
      ].map((label, i) => (
        <div key={label} className={done[i] ? "complete" : ""}>
          <span className="step-number">
            {done[i] ? <Check size={11} /> : i + 1}
          </span>
          <span>{label}</span>
          {i < 6 && <ChevronRight className="step-chevron" size={12} />}
        </div>
      ))}
    </div>
  );
}
