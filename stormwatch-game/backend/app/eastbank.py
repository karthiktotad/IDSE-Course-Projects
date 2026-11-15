"""Deterministic Eastbank grid authoring helpers.

Map coordinates are integer tile coordinates with origin at the northwest corner.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

WIDTH = 32
HEIGHT = 24
TILE_SIZE = 32
SEED = 2406


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    kind: str
    x: int
    y: int
    width: int = 1
    height: int = 1


LOCATIONS = [
    Location("eastbank-hospital", "Eastbank General Hospital", "hospital", 13, 13, 2, 2),
    Location("eastbank-school", "Eastbank School", "school", 24, 6, 2, 2),
    Location("eastbank-control", "Flood Control Centre", "control_centre", 25, 15, 2, 2),
    Location("eastbank-homes-north", "Northbank Homes", "residential", 8, 3, 2, 2),
    Location("eastbank-homes-central", "Canal View Homes", "residential", 18, 10, 2, 2),
    Location("eastbank-homes-south", "Lowbank Homes", "residential", 19, 19, 2, 2),
    Location("eastbank-clinic", "Riverside Clinic", "clinic", 6, 17, 2, 2),
    Location("weather-north", "Weather Station North", "weather_station", 5, 2),
    Location("weather-east", "Weather Station East", "weather_station", 29, 5),
    Location("weather-central", "Weather Station Central", "weather_station", 17, 8),
    Location("weather-south", "Weather Station South", "weather_station", 28, 21),
]


def _river_x(y: int) -> int:
    return 2 if y < 5 else 3 if y < 12 else 2 if y < 18 else 3


def _road_cells() -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    # Connected east-west spine and north-south boulevard, with local access streets.
    for y in (5, 12, 17):
        cells.update((x, y) for x in range(32))
    for x in (8, 15, 23, 29):
        cells.update((x, y) for y in range(1, 23))
    # Short street branches connect facility frontages to the road network.
    for y in range(8, 12):
        cells.add((12, y))
    for y in range(13, 17):
        cells.add((12, y))
    for x in range(15, 23):
        cells.add((x, 9))
    for x in range(23, 29):
        cells.add((x, 19))
    for y in range(6, 9):
        cells.add((27, y))
    # West-side clinic access bridge and east-side canal bridge.
    cells.update((x, 17) for x in range(3, 9))
    cells.update((x, 13) for x in range(20, 25))
    # Causeway crossing the drainage channel.
    cells.update((x, 10) for x in range(8, 16))
    return cells


def _building_cells() -> dict[tuple[int, int], str]:
    buildings: dict[tuple[int, int], str] = {}
    roads = _road_cells()
    for location in LOCATIONS:
        if location.kind in {"weather_station"}:
            continue
        for y in range(location.y, location.y + location.height):
            for x in range(location.x, location.x + location.width):
                if (x, y) not in roads:
                    buildings[(x, y)] = location.id
    # Additional homes give the district a lived-in, dense urban fabric.
    blocks = [(5, 7), (10, 2), (18, 3), (20, 7), (5, 20), (10, 20), (26, 9), (27, 11)]
    for index, (x0, y0) in enumerate(blocks, start=1):
        for y in range(y0, y0 + 2):
            for x in range(x0, x0 + 2):
                if (x, y) not in buildings and (x, y) not in roads:
                    buildings[(x, y)] = f"eastbank-residence-{index:02d}"
    return buildings


def build_map_document() -> dict:
    roads = _road_cells()
    buildings = _building_cells()
    inlets = {(7, 5), (14, 12), (22, 12), (15, 17), (28, 17), (8, 10), (23, 19), (5, 17)}
    station_positions = {(p.x, p.y): p.id for p in LOCATIONS if p.kind == "weather_station"}
    cells = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            rx = _river_x(y)
            in_river = x <= rx
            in_canal = 9 <= y <= 10 and 3 <= x <= 15
            on_road = (x, y) in roads
            building_id = buildings.get((x, y))
            station_id = station_positions.get((x, y))

            if in_river:
                terrain, elevation, impervious, infiltration, drainage, flows = "river", 250 + ((x * 37 + y * 19) % 180), 0.0, 0.0, 95.0, True
            elif in_canal:
                terrain, elevation, impervious, infiltration, drainage, flows = "canal", 410 + ((x * 29 + y * 13) % 160), 0.0, 0.0, 78.0, True
            elif building_id:
                terrain, elevation, impervious, infiltration, drainage, flows = "building", 1050 + ((x * 61 + y * 43) % 700), 1.0, 0.0, 1.8, False
            elif on_road:
                # The hospital approach at (12,12)-(12,16) is deliberately low.
                low_approach = x == 12 and 12 <= y <= 16
                terrain, elevation, impervious, infiltration, drainage, flows = "road", (620 + ((x * 23 + y * 17) % 90)) if low_approach else 1180 + ((x * 67 + y * 31) % 850), 0.94, 0.5, 7.5, True
            elif station_id:
                terrain, elevation, impervious, infiltration, drainage, flows = "grass", 1700 + ((x * 47 + y * 29) % 500), 0.32, 12.0, 3.0, True
            else:
                terrain = "park" if ((x + 2 * y) % 13 in (0, 1, 2) or (4 <= x <= 6 and 13 <= y <= 15)) else "grass"
                elevation = 720 + ((x * 97 + y * 71 + (x * y) % 89) % 1820)
                impervious = 0.16 if terrain == "park" else 0.24
                infiltration, drainage, flows = (22.0 if terrain == "park" else 15.0), 4.0, True

            district = "riverward" if x < 11 else "canalward" if x < 21 else "eastbank"
            cell = {
                "x": x, "y": y, "terrain_type": terrain,
                "elevation_mm": elevation, "impervious_ratio": impervious,
                "infiltration_rate_mm_hr": infiltration,
                "drainage_capacity_mm_hr": drainage,
                "building_id": building_id, "district_id": district,
                "can_water_flow": flows,
                "is_road": on_road,
                "is_bridge": on_road and (in_river or in_canal),
            }
            if (x, y) in inlets:
                cell["interactive_object_id"] = f"drain-{x:02d}-{y:02d}"
                cell["drainage_capacity_mm_hr"] = 34.0
            if station_id:
                cell["interactive_object_id"] = station_id
            cells.append(cell)
    return {
        "map_id": "eastbank",
        "name": "Eastbank",
        "columns": WIDTH,
        "rows": HEIGHT,
        "tile_size_px": TILE_SIZE,
        "pixel_width": WIDTH * TILE_SIZE,
        "pixel_height": HEIGHT * TILE_SIZE,
        "seed": SEED,
        "coordinate_system": "integer tile coordinates from northwest origin; x east, y south",
        "layers": ["base_terrain", "grass_natural", "river_drainage", "roads_bridges", "buildings", "important_locations", "interactive_objects", "flood_overlay"],
        "locations": [asdict(place) for place in LOCATIONS],
        "cells": cells,
    }
