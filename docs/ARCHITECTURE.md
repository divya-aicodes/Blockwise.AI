# BLOCKWISE — Final Architecture

This repository is a deterministic decision-support MVP using synthetic data.

```text
Stage 1: CSV data + NetworkX graph + RandomForest models + traffic profile
    -> Stage 2: occupancy conflicts + OR-Tools CP-SAT alternatives
    -> Stage 3: SimPy 24-hour simulation + simulated feedback
    -> Stage 4: React/Three.js + crew management (auth, work orders, checklists)
    -> Stage 5: cross-stage validation, hardening and end-to-end tests
```

Runtime contract:

```text
asset_id -> risk -> maintenance_id -> conflicts -> plan_id -> simulation -> feedback -> human decision
```

The only modeled route is `NDLS -> RE -> AWR -> BKI -> JP` with sections
`SEC-NDLS-RE`, `SEC-RE-AWR`, `SEC-AWR-BKI`, and `SEC-BKI-JP`. The graph is
linear, so every plan reports `reroute_available: false`; the system never
fabricates a route.

FastAPI loads datasets, graph and model artifacts once during application
startup. CP-SAT uses integer minutes relative to its planning horizon, while
SimPy uses minutes and the API uses offset-aware ISO-8601 timestamps. SQLite
crew-management tables are initialized additively for local deployments.

Human approval records immutable plan/simulation evidence and never starts
railway execution. Work-order execution is separately authenticated and
stateful. No output is a real railway safety certification or operational
accuracy claim.
