import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowLeft,
  Activity,
  Clock3,
  ShieldCheck,
} from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useAppStore } from "../store/useAppStore";
import type { Traffic, RiskLevel } from "../types";
import { titleCase, riskColors } from "../lib";
import RiskBadge from "../components/RiskBadge";
export default function AssetPage() {
  const { id } = useParams();
  const s = useAppStore();
  const asset = s.assets.find((a) => a.asset_id === id);
  const [traffic, setTraffic] = useState<Traffic | null>(null),
    [trafficError, setTrafficError] = useState("");
  useEffect(() => {
    if (asset) {
      s.selectAsset(asset.asset_id);
      const now = new Date();
      const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: "Asia/Kolkata",
        hour: "numeric",
        weekday: "short",
        hourCycle: "h23",
      }).formatToParts(now);
      const hour = Number(parts.find((p) => p.type === "hour")?.value);
      const weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].indexOf(
        parts.find((p) => p.type === "weekday")?.value || "Mon",
      );
      let active = true;
      setTraffic(null);
      setTrafficError("");
      void api
        .get<Traffic>("/traffic/" + asset.section_id, {
          params: { hour, weekday },
        })
        .then((r) => {
          if (active) setTraffic(r.data);
        })
        .catch((e) => {
          if (active) setTrafficError(errorMessage(e));
        });
      return () => {
        active = false;
      };
    }
  }, [asset, s.selectAsset]);
  if (!asset)
    return (
      <div className="page empty-state">
        <h1>
          {s.initializing
            ? "Loading asset…"
            : id
              ? "Asset not found"
              : "Select an asset"}
        </h1>
        <p>Choose an asset from the corridor to inspect its condition.</p>
        <Link className="primary" to="/map">
          Open corridor <ArrowRight size={16} />
        </Link>
      </div>
    );
  const prediction = s.risks[asset.asset_id];
  return (
    <div className="page asset-page">
      <Link className="back-link" to="/map">
        <ArrowLeft size={14} /> Back to corridor
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ASSET INTELLIGENCE</span>
          <h1>
            {titleCase(asset.asset_type)}
            <span className="heading-mono">{asset.asset_id}</span>
          </h1>
          <p>
            {asset.section_id} <span className="text-dot">·</span> Synthetic
            asset record
          </p>
        </div>
        <RiskBadge risk={asset.risk_level} />
      </div>
      <div className="asset-layout">
        <section>
          <div className="condition-panel">
            <div>
              <span className="eyebrow">CONDITION ASSESSMENT</span>
              <div className="condition-value">
                {asset.condition_score}
                <span>/100</span>
              </div>
              <p>Recorded asset condition</p>
              <div className="condition-scale">
                <div style={{ width: asset.condition_score + "%" }} />
                <i style={{ left: asset.condition_score + "%" }} />
              </div>
              <div className="scale-labels">
                <span>Degraded</span>
                <span>Good condition</span>
              </div>
            </div>
            <div className="asset-specification">
              <ShieldCheck size={26} />
              <dl className="details-list">
                <div>
                  <dt>Asset age</dt>
                  <dd>{asset.age_years} years</dd>
                </div>
                <div>
                  <dt>Previous failures</dt>
                  <dd>{asset.previous_failures}</dd>
                </div>
                <div>
                  <dt>Criticality</dt>
                  <dd>{asset.criticality}</dd>
                </div>
                <div>
                  <dt>Weather input</dt>
                  <dd>{titleCase(asset.weather_condition)}</dd>
                </div>
              </dl>
            </div>
          </div>
          <section className="risk-section">
            <div className="section-heading">
              <div>
                <span className="eyebrow">MODEL ASSESSMENT</span>
                <h2>Asset risk distribution</h2>
              </div>
              <button
                className="secondary"
                disabled={!!s.busy}
                onClick={() => void s.predictRisk(asset)}
              >
                <Activity size={15} />
                {s.busy?.includes("risk")
                  ? "Calculating…"
                  : prediction
                    ? "Recalculate risk"
                    : "Calculate risk"}
              </button>
            </div>
            {prediction ? (
              <>
                <div className="risk-result">
                  <span>Predicted risk class</span>
                  <RiskBadge risk={prediction.risk_level} />
                </div>
                {(["LOW", "MEDIUM", "HIGH", "CRITICAL"] as RiskLevel[]).map(
                  (r) => (
                    <div className="probability-row" key={r}>
                      <label>{titleCase(r)}</label>
                      <div>
                        <span
                          style={{
                            width: prediction.probabilities[r] * 100 + "%",
                            background: riskColors[r],
                          }}
                        />
                      </div>
                      <b className="mono">
                        {(prediction.probabilities[r] * 100).toFixed(1)}%
                      </b>
                    </div>
                  ),
                )}
                <p className="muted text-sm">
                  Class probabilities from the existing risk model. These
                  describe risk classes, not failure probability.
                </p>
              </>
            ) : (
              <div className="risk-empty">
                <Activity size={28} />
                <p>
                  Calculate risk to see the model’s class probabilities for this
                  asset.
                </p>
              </div>
            )}
            {s.error && (
              <p role="alert" className="error">
                {s.error}
              </p>
            )}
          </section>
          <div className="history-panel">
            <Clock3 size={19} />
            <div>
              <h3>{asset.days_since_maintenance} days since maintenance</h3>
              <p>
                The asset record includes elapsed time and{" "}
                {asset.previous_failures} previous failures. Individual
                service-event history is not supplied by this endpoint.
              </p>
            </div>
          </div>
        </section>
        <aside className="operational-panel">
          <span className="eyebrow">OPERATIONAL CONTEXT</span>
          <h2>{asset.section_id.replace("SEC-", "").replaceAll("-", " → ")}</h2>
          <div className="traffic-reading">
            <Activity size={16} />
            <span>Expected traffic</span>
            <strong>
              {traffic ? traffic.expected_trains_per_hour.toFixed(1) : "—"}
              <small> trains / hour</small>
            </strong>
          </div>
          {traffic ? (
            <p className="muted text-sm">
              Historical traffic profile for{" "}
              {String(traffic.hour).padStart(2, "0")}:00 IST on{" "}
              {
                [
                  "Monday",
                  "Tuesday",
                  "Wednesday",
                  "Thursday",
                  "Friday",
                  "Saturday",
                  "Sunday",
                ][traffic.weekday]
              }
              .
            </p>
          ) : (
            <p className="muted">
              {trafficError || "Loading traffic profile…"}
            </p>
          )}
          <div className="divider" />
          <h3>Planning considerations</h3>
          <ul className="fact-list">
            <li>Condition score is {asset.condition_score} out of 100.</li>
            <li>
              The asset has {asset.previous_failures} recorded previous
              failures.
            </li>
            <li>
              Maintenance was last recorded {asset.days_since_maintenance} days
              ago.
            </li>
            <li>
              Required maintenance skill is derived from{" "}
              {titleCase(asset.asset_type)}.
            </li>
          </ul>
          <p className="notice">
            These are recorded input facts. The model does not provide a causal
            explanation.
          </p>
          <button className="primary full" onClick={s.openSheet}>
            Plan maintenance <ArrowRight size={16} />
          </button>
        </aside>
      </div>
    </div>
  );
}
