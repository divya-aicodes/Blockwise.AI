import { useState } from "react";
import { ArrowUpRight, Search, SlidersHorizontal, Route, Train as TrainIcon, Users, Calendar, RefreshCw, CloudSun, History } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import RailwayCorridor from "../components/RailwayCorridor";
import AssetCard from "../components/AssetCard";
import AssetInspector from "../components/AssetInspector";

export default function MapPage() {
  const s = useAppStore();
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<"assets" | "trains" | "timetable" | "crews" | "weather" | "history">("assets");

  const filters = ["All", "Track", "Signal", "OHE", "High risk", "Critical"];
  const filtered = s.assets.filter(
    (a) =>
      (filter === "All" ||
        (filter === "High risk" && a.risk_level === "HIGH") ||
        (filter === "Critical" && a.risk_level === "CRITICAL") ||
        a.asset_type === filter.toUpperCase()) &&
      (a.asset_id + " " + a.section_id + " " + a.asset_type)
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const selected = s.assets.find((a) => a.asset_id === s.selectedAssetId);
  const critical = s.assets.filter((a) => a.risk_level === "CRITICAL").length;
  const high = s.assets.filter((a) => a.risk_level === "HIGH").length;
  const attention = [...filtered].sort(
    (a, b) =>
      ({ CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 })[b.risk_level] -
      { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 }[a.risk_level],
  );

  const filteredTrains = s.trains.filter(
    (t) =>
      (t.train_id + " " + t.train_name + " " + t.section_id + " " + t.train_type)
        .toLowerCase()
        .includes(search.toLowerCase()),
  );

  const filteredTimetable = s.timetable.filter(
    (t) =>
      (t.train_id + " " + t.train_name + " " + t.section_id)
        .toLowerCase()
        .includes(search.toLowerCase()),
  );

  const filteredCrews = s.crews.filter(
    (c) =>
      (c.crew_id + " " + c.crew_name + " " + c.primary_skill + " " + c.secondary_skills)
        .toLowerCase()
        .includes(search.toLowerCase()),
  );

  const filteredWeather = s.weather.filter(
    (w) => (w.date + " " + w.weather_condition).toLowerCase().includes(search.toLowerCase()),
  );

  const filteredHistory = s.maintenanceHistory.filter(
    (job) =>
      (job.job_id + " " + job.asset_id + " " + job.section_id + " " + job.job_type + " " + job.crew_id)
        .toLowerCase()
        .includes(search.toLowerCase()),
  );

  return (
    <div className="page map-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">NETWORK OVERVIEW</span>
          <h1>
            Operations corridor<span className="heading-dot">.</span>
          </h1>
          <p>Synthetic asset condition, train movements, timetable and crew registers.</p>
        </div>
        <div className="page-actions">
          <button className="secondary" onClick={() => void s.initialize(true)} disabled={s.initializing}>
            <RefreshCw className={s.initializing ? "spin-icon" : ""} size={15} />
            {s.initializing ? "Refreshing…" : "Refresh backend data"}
          </button>
          <button
            className="secondary"
            onClick={() => {
              s.selectHighestRisk();
            }}
            disabled={!s.assets.length}
          >
            Inspect highest-risk asset <ArrowUpRight size={16} />
          </button>
        </div>
      </div>
      <div className="status-strip">
        <span>
          <b>{s.initializing ? "—" : s.assets.length}</b> assets monitored
        </span>
        <span>
          <b className="critical-text">{s.initializing ? "—" : critical}</b>{" "}
          critical
        </span>
        <span>
          <b className="high-text">{s.initializing ? "—" : high}</b> high risk
        </span>
        <span>
          <b>{s.initializing ? "—" : s.trains.length}</b> train movements
        </span>
        <span>
          <b>{s.initializing ? "—" : s.crews.length}</b> crews
        </span>
        <span>
          <b>{s.health?.maintenance_requirements ?? "—"}</b> maintenance
          requirements
        </span>
        <span className="strip-end">
          <span className="status-dot connected" /> Live Synthetic Backend
        </span>
      </div>
      {s.datasets && (
        <details className="dataset-status">
          <summary>
            <span className="status-dot connected" />
            {Object.keys(s.datasets).length} file-backed data sources refreshed
            <small>Database records are queried live</small>
          </summary>
          <div className="dataset-status-grid">
            {Object.entries(s.datasets).map(([name, value]) => (
              <span key={name}>
                <small>{name.replaceAll("_", " ")}</small>
                <b>{value}</b>
              </span>
            ))}
          </div>
        </details>
      )}
      <div className="map-workspace">
        <section className="map-main">
          <div className="map-toolbar">
            <div className="filter-group" aria-label="Asset filters">
              {filters.map((f) => (
                <button
                  key={f}
                  className={filter === f ? "active" : ""}
                  onClick={() => setFilter(f)}
                >
                  {f}
                </button>
              ))}
            </div>
            <span className="view-label">
              <SlidersHorizontal size={14} /> Isometric corridor view
            </span>
          </div>
          <RailwayCorridor
            assets={filtered}
            allAssets={s.assets}
            selectedId={s.selectedAssetId}
            onSelect={s.selectAsset}
            maintenance={s.maintenance}
          />
          <div className="asset-register">
            <div className="section-heading">
              <div className="register-tabs" role="tablist" aria-label="Corridor registers">
                <button
                  className={`tab-button ${tab === "assets" ? "active" : ""}`}
                  role="tab"
                  aria-selected={tab === "assets"}
                  onClick={() => setTab("assets")}
                >
                  <Route size={14} /> Asset register <span>{s.assets.length}</span>
                </button>
                <button
                  className={`tab-button ${tab === "trains" ? "active" : ""}`}
                  role="tab"
                  aria-selected={tab === "trains"}
                  onClick={() => setTab("trains")}
                >
                  <TrainIcon size={14} /> Train movements <span>{s.trains.length}</span>
                </button>
                <button
                  className={`tab-button ${tab === "timetable" ? "active" : ""}`}
                  role="tab"
                  aria-selected={tab === "timetable"}
                  onClick={() => setTab("timetable")}
                >
                  <Calendar size={14} /> Timetable <span>{s.timetable.length}</span>
                </button>
                <button
                  className={`tab-button ${tab === "crews" ? "active" : ""}`}
                  role="tab"
                  aria-selected={tab === "crews"}
                  onClick={() => setTab("crews")}
                >
                  <Users size={14} /> Crews <span>{s.crews.length}</span>
                </button>
                <button
                  className={`tab-button ${tab === "weather" ? "active" : ""}`}
                  role="tab"
                  aria-selected={tab === "weather"}
                  onClick={() => setTab("weather")}
                >
                  <CloudSun size={14} /> Weather <span>{s.weather.length}</span>
                </button>
                <button
                  className={`tab-button ${tab === "history" ? "active" : ""}`}
                  role="tab"
                  aria-selected={tab === "history"}
                  onClick={() => setTab("history")}
                >
                  <History size={14} /> Maintenance history <span>{s.maintenanceHistory.length}</span>
                </button>
              </div>
              <label className="search-box">
                <Search size={14} />
                <input
                  aria-label="Search synthetic register"
                  placeholder="Search ID, name, section or type"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
            </div>
            <div className="table-scroll">
              {tab === "assets" && (
                <table>
                  <thead>
                    <tr>
                      <th>Asset</th>
                      <th>Type</th>
                      <th>Section</th>
                      <th>Condition</th>
                      <th>Risk</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((a) => (
                      <tr
                        key={a.asset_id}
                        className={
                          selected?.asset_id === a.asset_id ? "selected" : ""
                        }
                      >
                        <td>
                          <button
                            className="table-link mono"
                            onClick={() => s.selectAsset(a.asset_id)}
                          >
                            {a.asset_id}
                          </button>
                        </td>
                        <td>{a.asset_type.replaceAll("_", " ")}</td>
                        <td className="mono text-xs">{a.section_id}</td>
                        <td>
                          {a.condition_score}
                          <span className="muted"> /100</span>
                        </td>
                        <td>
                          <span
                            className={
                              "risk-text risk-" + a.risk_level.toLowerCase()
                            }
                          >
                            {a.risk_level}
                          </span>
                        </td>
                        <td>
                          <button
                            className="icon-button"
                            aria-label={"Select " + a.asset_id}
                            onClick={() => s.selectAsset(a.asset_id)}
                          >
                            <ArrowUpRight size={15} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {tab === "trains" && (
                <table>
                  <thead>
                    <tr>
                      <th>Train ID</th>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Section</th>
                      <th>Date</th>
                      <th>Scheduled</th>
                      <th>Actual</th>
                      <th>Delay</th>
                      <th>Priority</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTrains.slice(0, 100).map((t, idx) => (
                      <tr key={t.train_id + "-" + t.section_id + "-" + idx}>
                        <td className="mono font-bold">{t.train_id}</td>
                        <td>{t.train_name}</td>
                        <td>{t.train_type}</td>
                        <td className="mono text-xs">{t.section_id}</td>
                        <td>{t.date}</td>
                        <td className="mono text-xs">{t.scheduled_entry_time} — {t.scheduled_exit_time}</td>
                        <td className="mono text-xs">{t.actual_entry_time} — {t.actual_exit_time}</td>
                        <td>
                          <span className={t.delay_min > 15 ? "risk-text risk-high" : "risk-text risk-low"}>
                            {t.delay_min} min
                          </span>
                        </td>
                        <td>{t.priority}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {tab === "timetable" && (
                <table>
                  <thead>
                    <tr>
                      <th>Train ID</th>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Section</th>
                      <th>Scheduled Entry</th>
                      <th>Scheduled Exit</th>
                      <th>Priority</th>
                      <th>Running Days</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTimetable.map((t, idx) => (
                      <tr key={t.train_id + "-" + t.section_id + "-" + idx}>
                        <td className="mono font-bold">{t.train_id}</td>
                        <td>{t.train_name}</td>
                        <td>{t.train_type}</td>
                        <td className="mono text-xs">{t.section_id}</td>
                        <td className="mono text-xs">{t.scheduled_entry_time}</td>
                        <td className="mono text-xs">{t.scheduled_exit_time}</td>
                        <td>{t.priority}</td>
                        <td><span className="mono text-xs">{t.running_days}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {tab === "crews" && (
                <table>
                  <thead>
                    <tr>
                      <th>Crew ID</th>
                      <th>Name</th>
                      <th>Primary Skill</th>
                      <th>Secondary Skills</th>
                      <th>Shift</th>
                      <th>Size</th>
                      <th>Availability</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCrews.map((c) => (
                      <tr key={c.crew_id}>
                        <td className="mono font-bold">{c.crew_id}</td>
                        <td>{c.crew_name}</td>
                        <td><span className="risk-badge risk-low">{c.primary_skill}</span></td>
                        <td className="text-xs">{c.secondary_skills || "—"}</td>
                        <td className="mono text-xs">{c.shift_start} — {c.shift_end}</td>
                        <td>{c.crew_size} members</td>
                        <td>
                          <span className={c.availability === "AVAILABLE" ? "risk-text risk-low" : "risk-text risk-medium"}>
                            {c.availability}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {tab === "weather" && (
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Condition</th>
                      <th>Temperature</th>
                      <th>Rainfall</th>
                      <th>Visibility</th>
                      <th>Wind speed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredWeather.map((w) => (
                      <tr key={w.date}>
                        <td className="mono font-bold">{w.date}</td>
                        <td>{w.weather_condition.replaceAll("_", " ")}</td>
                        <td>{w.temperature_c} °C</td>
                        <td>{w.rainfall_mm} mm</td>
                        <td>{w.visibility_km} km</td>
                        <td>{w.wind_speed_kmh} km/h</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {tab === "history" && (
                <table>
                  <thead>
                    <tr>
                      <th>Job</th>
                      <th>Asset</th>
                      <th>Section</th>
                      <th>Work type</th>
                      <th>Condition</th>
                      <th>Crew</th>
                      <th>Weather</th>
                      <th>Historical</th>
                      <th>Actual duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredHistory.map((job) => (
                      <tr key={job.job_id}>
                        <td className="mono font-bold">{job.job_id}</td>
                        <td className="mono">{job.asset_id}</td>
                        <td className="mono text-xs">{job.section_id}</td>
                        <td>{job.job_type}</td>
                        <td>{job.asset_condition} /100</td>
                        <td>{job.crew_id} · {job.crew_size}</td>
                        <td>{job.weather_condition.replaceAll("_", " ")}</td>
                        <td>{job.historical_duration} min</td>
                        <td>{job.duration_min} min</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {!filtered.length && tab === "assets" && (
                <div className="empty-state">
                  {s.initializing
                    ? "Loading corridor assets…"
                    : "No assets match the current filters."}
                </div>
              )}
              {!filteredTrains.length && tab === "trains" && (
                <div className="empty-state">No train movements match the current search.</div>
              )}
              {!filteredTimetable.length && tab === "timetable" && (
                <div className="empty-state">No timetable entries match the current search.</div>
              )}
              {!filteredCrews.length && tab === "crews" && (
                <div className="empty-state">No crew records match the current search.</div>
              )}
              {!filteredWeather.length && tab === "weather" && (
                <div className="empty-state">No weather observations match the current search.</div>
              )}
              {!filteredHistory.length && tab === "history" && (
                <div className="empty-state">No maintenance history matches the current search.</div>
              )}
            </div>
          </div>
        </section>
        <aside className="map-inspector">
          {selected ? (
            <AssetInspector asset={selected} />
          ) : (
            <div className="inspector-intro">
              <Route size={24} />
              <h2>
                Every asset.
                <br />
                In context.
              </h2>
              <p>
                Select a marker or an asset below to inspect condition and plan
                maintenance.
              </p>
            </div>
          )}
          <div className="attention-list">
            <div className="section-heading">
              <h3>Requiring attention</h3>
              <span className="count">
                {
                  attention.filter((a) =>
                    ["HIGH", "CRITICAL"].includes(a.risk_level),
                  ).length
                }
              </span>
            </div>
            {attention
              .filter((a) => ["HIGH", "CRITICAL"].includes(a.risk_level))
              .slice(0, 6)
              .map((a) => (
                <AssetCard
                  key={a.asset_id}
                  asset={a}
                  selected={a.asset_id === s.selectedAssetId}
                  onSelect={() => s.selectAsset(a.asset_id)}
                />
              ))}
          </div>
          <div className="inspector-note">
            <span className="eyebrow">MAINTENANCE CONTEXT</span>
            <p>
              {s.maintenance
                ? `${s.maintenance.maintenance_id} · ${s.maintenance.section_id}`
                : "No requirement selected in this session."}
            </p>
            <small>
              Planning context only. Recorded approval does not start railway
              work.
            </small>
          </div>
        </aside>
      </div>
    </div>
  );
}
