import { useState } from "react";
import { ArrowUpRight, Search, SlidersHorizontal, Route } from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import RailwayCorridor from "../components/RailwayCorridor";
import AssetCard from "../components/AssetCard";
import AssetInspector from "../components/AssetInspector";
export default function MapPage() {
  const s = useAppStore();
  const [filter, setFilter] = useState("All"),
    [search, setSearch] = useState("");
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
  return (
    <div className="page map-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">NETWORK OVERVIEW</span>
          <h1>
            Operations corridor<span className="heading-dot">.</span>
          </h1>
          <p>Asset condition, maintenance context and the route ahead.</p>
        </div>
        <button
          className="secondary"
          onClick={() => {
            s.startDemo();
          }}
          disabled={!s.assets.length}
        >
          Start guided demo <ArrowUpRight size={16} />
        </button>
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
          <b>{s.health?.maintenance_requirements ?? "—"}</b> maintenance
          requirements
        </span>
        <span className="strip-end">
          <span className="status-dot connected" /> Stage 1 dataset
        </span>
      </div>
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
              <SlidersHorizontal size={14} /> Isometric view
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
              <div>
                <h2>Asset register</h2>
                <span className="muted text-sm">
                  Select an asset to locate it on the corridor.
                </span>
              </div>
              <label className="search-box">
                <Search size={14} />
                <input
                  aria-label="Search assets"
                  placeholder="Search ID, type or section"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
            </div>
            <div className="table-scroll">
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
              {!filtered.length && (
                <div className="empty-state">
                  {s.initializing
                    ? "Loading corridor assets…"
                    : "No assets match the current filters."}
                </div>
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
