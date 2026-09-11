# BLOCKWISE — Railway Maintenance Decision-Support Platform (Stages 1 to 4)

This repository implements the New Delhi to Jaipur corridor data, prediction, conflict-detection, maintenance-planning, deterministic digital-twin backend, and a human-centered Stage 4 operations dashboard. All train operations, delays, asset conditions, maintenance records, weather observations, and simulated outcomes are synthetic. Station names, station codes, route order, and approximate distances are the only real-world route references.

Stage 2 reuses every Stage 1 dataset and trained pipeline. Stage 3 consumes persisted Stage 2 plans and tests them in a repeatable 24-hour SimPy batch simulation. Stage 4 adds a responsive React/Three.js workflow for asset inspection, risk prediction, maintenance creation, conflict review, alternative comparison, playback, simulation feedback, and evidence-backed human decisions. It does not retrain models, create a second dataset, fabricate reroutes, stream telemetry, or represent simulated feedback as real railway observations.

## Corridor

```text
NDLS --84 km-- RE --74 km-- AWR --61 km-- BKI --90 km-- JP
```

| Section | From | To | Distance | Maximum speed |
|---|---:|---:|---:|---:|
| `SEC-NDLS-RE` | NDLS | RE | 84 km | 130 km/h |
| `SEC-RE-AWR` | RE | AWR | 74 km | 120 km/h |
| `SEC-AWR-BKI` | AWR | BKI | 61 km | 110 km/h |
| `SEC-BKI-JP` | BKI | JP | 90 km | 130 km/h |

The NetworkX graph has only this linear route. Every returned plan therefore sets `reroute_available` to `false`.

## Stage 2 workflow

```text
Create maintenance requirement
  → propose or select a maintenance window
  → detect section-occupancy conflicts
  → load trains, crews, traffic, and asset risk
  → run OR-Tools CP-SAT
  → generate distinct feasible candidates
  → calculate metrics
  → score and rank best to worst
```

Safety, minimum duration, planning bounds, crew skill, crew availability, complete shift coverage, same-section exclusion, and crew double-booking are hard constraints. Train delay, preferred-start delay, risk exposure, traffic density, and crew cost are objective trade-offs.

Historical windows use actual movement times from `trains.csv`. Dates outside the 90-day history use `timetable_base.csv` projected onto the requested date and filtered by `running_days`; historical actual delays are never presented as future predictions.

All API planning timestamps must include a UTC offset. Examples use India Standard Time (`+05:30`). Intervals are half-open: a train exiting exactly when maintenance begins is not a conflict.

## Stage 3 workflow

```text
Select persisted ranked plan
  → project the Stage 1 timetable onto one operating date
  → create controlled SimPy section resources
  → move each train through all four sections in corridor order
  → apply the Stage 2 train delays and maintenance block
  → collect train, maintenance, safety, and KPI results
  → compare predicted values with simulated actual outcomes
  → atomically store feedback for future retraining work
```

The section closure is a hard constraint: maintenance and a train cannot occupy the same section. Maintenance execution uncertainty is a deterministic variation of at most five minutes based on `plan_id`, simulation date, and seed. Identical inputs therefore produce identical simulation output. The simulator never changes Stage 1 models or claims feedback as field accuracy.

## Setup and execution

Python 3.11 or newer is required.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run_pipeline.py
```

The pipeline regenerates and validates Stage 1 artifacts, trains the existing Stage 1 models, builds the traffic profile, then smoke-tests Stage 1, all three Stage 2 endpoints, a full Stage 3 plan simulation, and feedback persistence before starting Uvicorn. Use `python run_pipeline.py --no-serve` to validate and exit.

Interactive API documentation is available at `http://127.0.0.1:8000/docs` after startup.

## API

Stage 1 routes remain available:

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Confirms every required artifact and repository loaded |
| GET | `/assets` | Returns synthetic assets |
| GET | `/trains` | Returns movements; filters: `section`, `date`, `train_id` |
| POST | `/predict-risk` | Returns risk class and normalized probabilities |
| POST | `/predict-duration` | Returns predicted maintenance duration |
| GET | `/traffic/{section}` | Returns expected trains/hour |

Stage 2 routes:

| Method | Route | Purpose |
|---|---|---|
| POST | `/create-maintenance` | Resolves the asset section and stores an `M001`-style requirement |
| POST | `/detect-conflicts` | Returns structured occupancy conflicts without optimizing |
| POST | `/generate-alternatives` | Returns zero to five safe, distinct, scored plans |

Stage 3 routes:

| Method | Route | Purpose |
|---|---|---|
| POST | `/simulate-plan` | Runs a persisted `P001`-style Stage 2 plan for one operating date |
| GET | `/feedback-stats` | Returns aggregate simulated prediction error; optional `last_n` filter |

Create a requirement:

```json
{
  "asset_id": "AST-01-01",
  "job_type": "INSPECTION",
  "urgency": "HIGH",
  "minimum_duration_min": 60,
  "preferred_start_time": "2026-09-01T08:00:00+05:30",
  "earliest_start_time": "2026-09-01T06:00:00+05:30",
  "latest_end_time": "2026-09-02T06:00:00+05:30"
}
```

If `minimum_duration_min` is omitted, the existing Stage 1 duration pipeline estimates it. The stored requirement always includes `maintenance_id`, asset and section IDs, job type, urgency, required skill, minimum duration, all three planning timestamps, and status.

Detect conflicts for a candidate window:

```json
{
  "maintenance_id": "M001",
  "section_id": "SEC-NDLS-RE",
  "start_time": "2026-09-01T08:00:00+05:30",
  "end_time": "2026-09-01T10:00:00+05:30"
}
```

Generate alternatives from the stored planning bounds:

```json
{
  "maintenance_id": "M001",
  "top_n": 5,
  "max_train_delay_min": 240,
  "existing_windows": []
}
```

When constraints are infeasible, the route returns HTTP 200 with `status: "NO_FEASIBLE_PLAN"`, zero alternatives, and an empty list. It never invents a fallback plan.

Simulate a returned plan:

```json
{
  "plan_id": "P001",
  "simulation_date": "2026-09-01",
  "random_seed": 42
}
```

The response includes maintenance execution, per-train/per-section timestamps, planned delay, additional simulation waiting, total and maximum delay, affected train IDs, completion status, and unresolved safety conflicts. `GET /feedback-stats?last_n=10` reports duration and delay MAE plus signed mean errors over stored simulations.

## Stage 4 operations dashboard

The Stage 4 frontend is a Vite + React + TypeScript application with a dark, keyboard-friendly operations shell. It uses Zustand for workflow state, Axios for API calls, Lucide icons, Framer Motion for restrained transitions, and React Three Fiber/Three.js for the interactive corridor schematic and digital-twin playback. The scene is a section-level operational schematic, not a geographic map.

Start the complete local demo:

```powershell
.\.venv\Scripts\python.exe run_stage4.py
```

Or start each service separately:

```powershell
# terminal 1, from the repository root
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# terminal 2
cd frontend
npm.cmd install
npm.cmd run dev
```

Open [http://127.0.0.1:5173/map](http://127.0.0.1:5173/map) for the guided workflow and [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the API. The workflow is intentionally human-in-the-loop: an operator inspects an asset, creates a requirement, reviews conflicts and ranked plans, runs the deterministic simulation, then records APPROVED, MODIFY, or REJECTED through `POST /plan-decision`. Approval stores an immutable plan/simulation evidence snapshot and SHA-256 hash; it does not start railway execution.

### Crew management

Open [http://127.0.0.1:5173/crew](http://127.0.0.1:5173/crew) for the bilingual (English/Hindi) crew workspace. Crew registration is inactive until an administrator approves the account. The `ADMIN` role has full access to the operational dashboard, planning, simulation, approvals, crew management, work orders, checklists, reports, and notifications. Other authenticated crew roles are restricted to their own assigned-work notifications; the frontend hides operational navigation and the API returns `403 Administrator access required` for operational requests. Configure `RAILWAY_JWT_SECRET` in production; set the three `RAILWAY_BOOTSTRAP_ADMIN_*` variables once to create the first active administrator, then remove the bootstrap password. Never commit `.env` files or database files.

Crew API flow:

```text
POST /auth/register                request an account (inactive by default)
POST /auth/login                   receive short-lived access + refresh tokens
POST /auth/approve                 ADMIN-only account approval
POST /work-orders                  ADMIN-only creation from an approved plan
POST /work-orders/{id}/assign      skill-checked crew assignment
GET  /checklists/{id}/validate     mandatory safety validation
GET  /notifications                user-scoped notifications
```

Crew approval and email workflow:

```text
Crew submits registration with employee ID, name, role and email
        ↓
Account is stored inactive (cannot sign in yet)
        ↓
Active administrators receive an APPROVAL_REQUIRED notification
        ↓
Crew receives an account-received email
        ↓
Admin dashboard polls for pending registrations and shows a new-registration alert
        ↓
Admin selects Approve
        ↓
Account becomes active and an approval notification + confirmation email are sent to that crew email
        ↓
Crew signs in and sees only administrator-issued assigned-work notifications
```

For local development, emails are written to `backend/app/data/email_outbox.jsonl` with `EMAIL_MODE=outbox`; this is an email preview/outbox, not a claim that an external email was delivered. For deployment, set `EMAIL_MODE=smtp`, `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_TLS`, `SMTP_USERNAME`, and `SMTP_PASSWORD` in the environment. SMTP failures are retained in the outbox with an error for retry/operations review.

Stage 4 endpoint groups are:

```text
POST /create-maintenance              create a maintenance requirement
POST /detect-conflicts               return section occupancy conflicts
POST /generate-alternatives           return ranked safe alternatives
POST /simulate-plan                  run the deterministic one-day twin
POST /plan-decision                   ADMIN-only evidence-backed decision
GET  /assets, /health, /feedback-stats supporting dashboard data
```

The dashboard labels synthetic data and simulation feedback in the UI. It is a prototype decision-support surface, not an authority to dispatch crews or alter a live railway timetable.

## Stage 5 final validation

Stage 5 audits and validates the full Stage 1 → Stage 4 contract. Run:

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --no-serve
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm.cmd test
npm.cmd run build
```

The acceptance test in `tests/test_stage5_e2e.py` exercises the real path from
asset selection and risk inference through maintenance creation, conflict
detection, CP-SAT plans, SimPy simulation, simulated feedback, and APPROVED
human decision. The project has no alternate route: the NDLS → RE → AWR → BKI
→ JP graph is linear and `reroute_available` is always false.

## Scoring

Lower is better. Weights are centralized in `optimization/scoring.py`:

```text
overall_score =
  1000 × safety_conflicts
  + 10 × priority_weighted_train_delay_min
  + 5 × maintenance_delay_min
  + risk_delay_penalty
  + crew_cost
```

Unsafe candidates are excluded regardless of numeric score. HIGH-priority train delay weighs more than MEDIUM, which weighs more than LOW. Risk reduction is a deterministic comparison metric based on synthetic Stage 1 asset risk, condition, urgency, and wait time; it is not a scientifically validated railway risk estimate.

## Performance design

- CSVs and model pipelines load once during application startup.
- Train filters use inverted indexes instead of rescanning all movements.
- Conflict detection scans only relevant section/date records: O(k), where k is relevant occupancy rows.
- Traffic lookup is O(1); CP-SAT traffic costs are precomputed per candidate minute.
- The sequential Stage 1 generator is O(days × trains × sections), which is necessary to propagate delays correctly.
- Writes to maintenance requirement storage are locked and atomic.
- Ranked alternatives receive stable IDs and are atomically stored as JSON.
- Simulation feedback CSV writes are locked and atomic; the full-day timetable is grouped once by train.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm.cmd test
npm.cmd run build
npm.cmd exec --yes playwright test
```

The suite covers Stage 1 compatibility; all four valid sections; actual-history versus future-timetable selection; conflict boundaries; Stage 2 planning constraints and endpoints; corridor ordering; sequential train movement; exclusive maintenance occupancy; planned and additional delay; unaffected sparse traffic; deterministic duration variation; KPI aggregation; all four simulation targets; persisted feedback and MAE math; and both Stage 3 endpoints.

The models and risk comparison metrics are prototype aids trained on synthetic data. They are not evidence of operational accuracy or authorization to execute railway work. Playwright exercises the complete browser workflow against the local backend, including responsive layouts, simulation playback, backend-offline recovery, and all three decision actions.
