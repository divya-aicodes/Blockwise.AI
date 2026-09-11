"""Shared corridor and domain constants."""

from typing import Final


STATIONS: Final[tuple[dict[str, object], ...]] = (
    {"code": "NDLS", "name": "New Delhi", "distance_from_origin_km": 0},
    {"code": "RE", "name": "Rewari", "distance_from_origin_km": 84},
    {"code": "AWR", "name": "Alwar", "distance_from_origin_km": 158},
    {"code": "BKI", "name": "Bandikui", "distance_from_origin_km": 219},
    {"code": "JP", "name": "Jaipur", "distance_from_origin_km": 309},
)

SECTIONS: Final[tuple[dict[str, object], ...]] = (
    {
        "section_id": "SEC-NDLS-RE",
        "from_station": "NDLS",
        "to_station": "RE",
        "distance_km": 84,
        "max_speed_kmh": 130,
    },
    {
        "section_id": "SEC-RE-AWR",
        "from_station": "RE",
        "to_station": "AWR",
        "distance_km": 74,
        "max_speed_kmh": 120,
    },
    {
        "section_id": "SEC-AWR-BKI",
        "from_station": "AWR",
        "to_station": "BKI",
        "distance_km": 61,
        "max_speed_kmh": 110,
    },
    {
        "section_id": "SEC-BKI-JP",
        "from_station": "BKI",
        "to_station": "JP",
        "distance_km": 90,
        "max_speed_kmh": 130,
    },
)

STATION_CODES: Final[frozenset[str]] = frozenset(
    str(station["code"]) for station in STATIONS
)
SECTION_IDS: Final[tuple[str, ...]] = tuple(
    str(section["section_id"]) for section in SECTIONS
)
SECTION_ID_SET: Final[frozenset[str]] = frozenset(SECTION_IDS)
TRAIN_TYPES: Final[tuple[str, ...]] = ("EXPRESS", "PASSENGER", "FREIGHT")
PRIORITIES: Final[tuple[str, ...]] = ("HIGH", "MEDIUM", "LOW")
CRITICALITIES: Final[tuple[str, ...]] = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
WEATHER_CONDITIONS: Final[tuple[str, ...]] = (
    "CLEAR",
    "CLOUDY",
    "LIGHT_RAIN",
    "HEAVY_RAIN",
    "FOG",
)
RISK_LEVELS: Final[tuple[str, ...]] = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
JOB_TYPES: Final[tuple[str, ...]] = (
    "INSPECTION",
    "PREVENTIVE",
    "CORRECTIVE",
    "EMERGENCY",
)

