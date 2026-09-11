from __future__ import annotations

from datetime import date

import pytest

from backend.app.constants import SECTION_IDS
from backend.app.graph.railway_graph import RailwayGraph
from backend.app.repository import CsvRepository
from backend.app.simulation.scenario_runner import run_scenario


@pytest.mark.parametrize("section_id", SECTION_IDS)
def test_full_day_runner_simulates_every_corridor_section(
    artifact_bundle: dict[str, object], section_id: str
) -> None:
    repository = CsvRepository.from_data_dir(artifact_bundle["data_dir"])
    graph = RailwayGraph.load_graph(artifact_bundle["graph_path"])
    plan = {
        "plan_id": "P001",
        "maintenance_id": "M001",
        "maintenance_window": {
            "start": "2026-09-01T02:00:00+05:30",
            "end": "2026-09-01T02:20:00+05:30",
        },
        "affected_trains": [],
        "total_train_delay_min": 0,
        "safety_conflicts": 0,
    }
    maintenance = {
        "maintenance_id": "M001",
        "section_id": section_id,
    }

    result = run_scenario(
        plan,
        date(2026, 9, 1),
        maintenance_requirement=maintenance,
        repository=repository,
        railway_graph=graph,
        random_seed=42,
    )

    assert result["section_id"] == section_id
    assert result["kpis"]["trains_simulated"] == 20
    assert result["kpis"]["maintenance_completed"] is True
    assert result["kpis"]["conflicts_detected"] == 0
    assert all(
        [event["section_id"] for event in train["section_events"]]
        == list(SECTION_IDS)
        for train in result["train_results"]
    )

