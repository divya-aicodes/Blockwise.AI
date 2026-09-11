"""NetworkX representation of the five-node railway corridor."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import networkx as nx

from backend.app.constants import SECTIONS, STATIONS


class RailwayGraph:
    """Small, validated graph with deterministic serialization."""

    def __init__(self, *, build_default: bool = True) -> None:
        self.graph = nx.Graph()
        if build_default:
            self._build_default_corridor()

    def _build_default_corridor(self) -> None:
        for station in STATIONS:
            code = str(station["code"])
            attributes = {key: value for key, value in station.items() if key != "code"}
            self.graph.add_node(code, **attributes)

        for section in SECTIONS:
            attributes = dict(section)
            self.graph.add_edge(
                str(section["from_station"]),
                str(section["to_station"]),
                **attributes,
            )
        self._validate()

    def _validate(self) -> None:
        if not nx.is_connected(self.graph):
            raise ValueError("Railway graph must be connected")
        for _, _, attributes in self.graph.edges(data=True):
            required = {
                "section_id",
                "from_station",
                "to_station",
                "distance_km",
                "max_speed_kmh",
            }
            missing = required.difference(attributes)
            if missing:
                raise ValueError(f"Graph edge is missing attributes: {sorted(missing)}")
            if float(attributes["distance_km"]) <= 0:
                raise ValueError("Section distance must be positive")
            if float(attributes["max_speed_kmh"]) <= 0:
                raise ValueError("Section maximum speed must be positive")

    def get_section_between(self, st1: str, st2: str) -> dict[str, Any]:
        """Return a copy of the section attributes between adjacent stations."""
        if st1 not in self.graph or st2 not in self.graph:
            unknown = sorted({station for station in (st1, st2) if station not in self.graph})
            raise ValueError(f"Unknown station code(s): {', '.join(unknown)}")
        attributes = self.graph.get_edge_data(st1, st2)
        if attributes is None:
            raise ValueError(f"No direct section exists between {st1} and {st2}")
        return dict(attributes)

    def get_all_sections(self) -> list[dict[str, Any]]:
        """Return sections in physical corridor order."""
        by_id = {
            str(attributes["section_id"]): dict(attributes)
            for _, _, attributes in self.graph.edges(data=True)
        }
        return [by_id[str(section["section_id"])] for section in SECTIONS]

    def get_path_stations(self, start: str, end: str) -> list[str]:
        """Return the distance-shortest station path between two control nodes."""
        if start not in self.graph or end not in self.graph:
            unknown = sorted({station for station in (start, end) if station not in self.graph})
            raise ValueError(f"Unknown station code(s): {', '.join(unknown)}")
        return list(nx.shortest_path(self.graph, start, end, weight="distance_km"))

    def save_graph(self, path: str | Path) -> None:
        """Atomically persist a stable JSON representation."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "directed": False,
            "nodes": [
                {"code": code, **dict(attributes)}
                for code, attributes in sorted(self.graph.nodes(data=True))
            ],
            "sections": self.get_all_sections(),
        }
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(payload, temporary_file, indent=2, sort_keys=True)
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, destination)

    @classmethod
    def load_graph(cls, path: str | Path) -> "RailwayGraph":
        """Load and validate a graph written by :meth:`save_graph`."""
        source = Path(path)
        with source.open("r", encoding="utf-8") as graph_file:
            payload = json.load(graph_file)
        if payload.get("schema_version") != 1 or payload.get("directed") is not False:
            raise ValueError("Unsupported graph JSON schema")

        instance = cls(build_default=False)
        for node in payload.get("nodes", []):
            node = dict(node)
            code = node.pop("code")
            instance.graph.add_node(code, **node)
        for section in payload.get("sections", []):
            section = dict(section)
            instance.graph.add_edge(
                section["from_station"], section["to_station"], **section
            )
        instance._validate()
        return instance


def build_and_save_graph(path: str | Path) -> RailwayGraph:
    """Build the corridor, verify its canonical route, and save it."""
    railway_graph = RailwayGraph()
    expected = ["NDLS", "RE", "AWR", "BKI", "JP"]
    actual = railway_graph.get_path_stations("NDLS", "JP")
    if actual != expected:
        raise ValueError(f"Unexpected corridor path: {actual}")
    railway_graph.save_graph(path)
    return railway_graph

