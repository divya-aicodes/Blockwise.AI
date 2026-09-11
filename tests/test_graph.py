from __future__ import annotations

import pytest

from backend.app.graph.railway_graph import RailwayGraph


def test_corridor_path_and_section_attributes() -> None:
    graph = RailwayGraph()
    assert graph.get_path_stations("NDLS", "JP") == [
        "NDLS",
        "RE",
        "AWR",
        "BKI",
        "JP",
    ]
    assert graph.get_path_stations("JP", "NDLS") == [
        "JP",
        "BKI",
        "AWR",
        "RE",
        "NDLS",
    ]
    section = graph.get_section_between("NDLS", "RE")
    assert section["section_id"] == "SEC-NDLS-RE"
    assert section["distance_km"] == 84
    assert len(graph.get_all_sections()) == 4


def test_graph_round_trip(artifact_bundle: dict[str, object]) -> None:
    loaded = RailwayGraph.load_graph(artifact_bundle["graph_path"])
    assert loaded.get_path_stations("NDLS", "JP")[-1] == "JP"


def test_graph_rejects_unknown_station() -> None:
    with pytest.raises(ValueError, match="Unknown station"):
        RailwayGraph().get_path_stations("UNKNOWN", "JP")

