import { useAppStore } from "../store/useAppStore";
import type { AlternativePlan, SimulationResult } from "../types";
export default function FeedbackPanel({
  plan,
  result,
}: {
  plan: AlternativePlan;
  result: SimulationResult;
}) {
  const feedback = useAppStore((s) => s.feedback);
  const comparisons = [
    {
      label: "Maintenance duration",
      predicted: result.maintenance.predicted_duration_min,
      actual: result.maintenance.simulated_duration_min,
    },
    {
      label: "Total train delay",
      predicted: plan.total_train_delay_min,
      actual: result.kpis.total_delay_min,
    },
  ];
  return (
    <section className="feedback-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">PREDICTION → OUTCOME</span>
          <h2>Simulation feedback</h2>
        </div>
        <span className="demo-label">SYNTHETIC DIGITAL-TWIN FEEDBACK</span>
      </div>
      <div className="feedback-comparisons">
        {comparisons.map((c) => (
          <div key={c.label}>
            <h3>{c.label}</h3>
            <div className="comparison-bar">
              <span>Predicted</span>
              <div>
                <i
                  style={{
                    width:
                      (c.predicted / Math.max(c.predicted, c.actual, 1)) * 100 +
                      "%",
                  }}
                />
              </div>
              <b>{c.predicted} min</b>
            </div>
            <div className="comparison-bar actual">
              <span>Simulated</span>
              <div>
                <i
                  style={{
                    width:
                      (c.actual / Math.max(c.predicted, c.actual, 1)) * 100 +
                      "%",
                  }}
                />
              </div>
              <b>{c.actual} min</b>
            </div>
            <small className="muted">
              {c.actual - c.predicted >= 0 ? "+" : ""}
              {c.actual - c.predicted} min difference
            </small>
          </div>
        ))}
      </div>
      {feedback ? (
        <div className="feedback-stats">
          <span>
            Stored simulations <b>{feedback.total_simulations}</b>
          </span>
          <span>
            Duration MAE <b>{feedback.duration_mae_min} min</b>
          </span>
          <span>
            Delay MAE <b>{feedback.delay_mae_min} min</b>
          </span>
          <span>
            Mean duration error <b>{feedback.mean_duration_error_min} min</b>
          </span>
          <span>
            Mean delay error <b>{feedback.mean_delay_error_min} min</b>
          </span>
        </div>
      ) : (
        <p className="muted">Aggregate feedback statistics are unavailable.</p>
      )}
    </section>
  );
}
