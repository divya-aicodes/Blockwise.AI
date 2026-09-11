# BLOCKWISE — Deterministic Demo

1. Start the project with `start.bat`.
2. Open `http://127.0.0.1:5173/map`.
3. Select a HIGH or CRITICAL asset from the asset register.
4. Calculate risk, create a maintenance requirement, and open Planning.
5. Review conflicts, generate alternatives, and select rank 1.
6. Run the simulation and inspect train-delay and maintenance KPIs.
7. Record APPROVE, MODIFY, or REJECT. Approval is human-in-the-loop and
   remains a planning decision only.
8. Open `/crew` for the separate authenticated crew workspace.

All data, crew records, weather, train movements, and simulation outcomes are
synthetic. Repeatable simulation uses seed `42`; identical plan/date/seed
inputs produce the same result. Simulated feedback is not field feedback.
