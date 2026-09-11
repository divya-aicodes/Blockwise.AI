import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { defaultWindow, localInput, titleCase, toIST } from "../lib";
import Modal from "./Modal";
export default function MaintenanceForm() {
  const s = useAppStore(),
    navigate = useNavigate();
  const asset = s.assets.find((a) => a.asset_id === s.selectedAssetId);
  const previous =
    s.maintenance?.asset_id === asset?.asset_id ? s.maintenance : null;
  const [form, setForm] = useState(() =>
    previous
      ? {
          job_type: previous.job_type,
          urgency: previous.urgency,
          earliest_start_time: localInput(previous.earliest_start_time),
          preferred_start_time: localInput(previous.preferred_start_time),
          latest_end_time: localInput(previous.latest_end_time),
        }
      : {
          job_type: "INSPECTION",
          urgency: asset?.risk_level === "CRITICAL" ? "EMERGENCY" : "HIGH",
          ...defaultWindow(),
        },
  );
  const [duration, setDuration] = useState("");
  const [validation, setValidation] = useState("");
  if (!asset) return null;
  const change = (key: keyof typeof form, value: string) =>
    setForm((f) => ({ ...f, [key]: value }));
  async function submit(e: FormEvent) {
    e.preventDefault();
    setValidation("");
    const early = Date.parse(toIST(form.earliest_start_time)),
      preferred = Date.parse(toIST(form.preferred_start_time)),
      latest = Date.parse(toIST(form.latest_end_time));
    if (!(early <= preferred && preferred < latest)) {
      setValidation("Preferred start must fall inside the planning horizon.");
      return;
    }
    if (
      await s.createMaintenance({
        asset_id: asset!.asset_id,
        job_type: form.job_type,
        urgency: form.urgency,
        earliest_start_time: toIST(form.earliest_start_time),
        preferred_start_time: toIST(form.preferred_start_time),
        latest_end_time: toIST(form.latest_end_time),
        ...(duration ? { minimum_duration_min: Number(duration) } : {}),
      })
    )
      navigate("/plan");
  }
  return (
    <Modal
      title={previous ? "Revise maintenance requirement" : "Plan maintenance"}
      onClose={s.closeSheet}
    >
      <form onSubmit={submit} className="maintenance-form">
        <div className="form-context">
          <span className="mono">{asset.asset_id}</span>
          <b>{titleCase(asset.asset_type)}</b>
          <small>{asset.section_id}</small>
        </div>
        <div className="form-grid">
          <label>
            Job type
            <select
              value={form.job_type}
              onChange={(e) => change("job_type", e.target.value)}
            >
              {["INSPECTION", "PREVENTIVE", "CORRECTIVE", "EMERGENCY"].map(
                (t) => (
                  <option key={t}>{t}</option>
                ),
              )}
            </select>
          </label>
          <label>
            Urgency
            <select
              value={form.urgency}
              onChange={(e) => change("urgency", e.target.value)}
            >
              {["LOW", "NORMAL", "HIGH", "EMERGENCY"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Required skill{" "}
          <span className="derived">
            <LockKeyhole size={13} />
            {asset.asset_type} · derived from asset
          </span>
        </label>
        <div className="divider" />
        <span className="eyebrow">PLANNING WINDOW · INDIA STANDARD TIME</span>
        <label>
          Earliest start
          <input
            type="datetime-local"
            required
            value={form.earliest_start_time}
            onChange={(e) => change("earliest_start_time", e.target.value)}
          />
        </label>
        <label>
          Preferred start
          <input
            type="datetime-local"
            required
            value={form.preferred_start_time}
            onChange={(e) => change("preferred_start_time", e.target.value)}
          />
        </label>
        <label>
          Latest completion
          <input
            type="datetime-local"
            required
            value={form.latest_end_time}
            onChange={(e) => change("latest_end_time", e.target.value)}
          />
        </label>
        <details>
          <summary>Duration override · optional</summary>
          <label>
            Minimum duration (minutes)
            <input
              type="number"
              min="1"
              max="720"
              value={duration}
              placeholder="Use backend duration prediction"
              onChange={(e) => setDuration(e.target.value)}
            />
          </label>
        </details>
        <p className="muted text-sm">
          The duration model estimates the work when no override is supplied.
          The optimizer assigns a qualified crew.
        </p>
        {previous && (
          <p className="notice">
            A revision creates a new requirement. Existing decisions remain
            attached to the previous plan.
          </p>
        )}
        {(validation || s.error) && (
          <div role="alert" className="error">
            {validation || s.error}
          </div>
        )}
        <button className="primary full" disabled={!!s.busy} type="submit">
          {s.busy || "Create requirement"}
          {!s.busy && <ArrowRight size={16} />}
        </button>
      </form>
    </Modal>
  );
}
