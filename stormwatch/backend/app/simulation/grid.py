"""Grid loading and cell arrays for the simplified Eastbank flood model."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

FloatGrid = NDArray[np.float64]
BoolGrid = NDArray[np.bool_]


@dataclass
class SimulationGrid:
    width: int
    height: int
    cell_size_m: float
    elevation_mm: FloatGrid
    impervious_ratio: FloatGrid
    infiltration_rate_mm_hr: FloatGrid
    drainage_capacity_mm_hr: FloatGrid
    terrain_type: NDArray[np.str_]
    cell_type: NDArray[np.str_]
    building_id: NDArray[np.str_]
    district_id: NDArray[np.str_]
    is_road: BoolGrid
    can_water_flow: BoolGrid
    is_drain_inlet: BoolGrid
    water_depth_mm: FloatGrid

    @property
    def cell_area_m2(self) -> float:
        return self.cell_size_m * self.cell_size_m

    @property
    def flow_mask(self) -> BoolGrid:
        return self.can_water_flow & (self.cell_type != "obstacle")

    @property
    def waterway_mask(self) -> BoolGrid:
        return (self.terrain_type == "river") | (self.terrain_type == "canal")

    def volume_m3(self, depth_mm: FloatGrid | None = None) -> float:
        depths = self.water_depth_mm if depth_mm is None else depth_mm
        return float(np.sum(depths, dtype=np.float64) * self.cell_area_m2 / 1000.0)


def default_grid_path() -> Path:
    # backend/app/simulation/grid.py -> project root -> shared/eastbank_grid.json
    return Path(__file__).resolve().parents[3] / "shared" / "eastbank_grid.json"


def load_grid(path: str | Path | None = None) -> tuple[SimulationGrid, dict]:
    """Load the shared map and validate that it forms a complete orthogonal grid."""
    map_path = Path(path) if path is not None else default_grid_path()
    document = json.loads(map_path.read_text(encoding="utf-8"))
    width, height = int(document["columns"]), int(document["rows"])
    tile_px = int(document["tile_size_px"])
    cells = document["cells"]
    if len(cells) != width * height:
        raise ValueError(f"Expected {width * height} grid cells, found {len(cells)}")

    shape = (height, width)
    elevation = np.zeros(shape, dtype=np.float64)
    impervious = np.zeros(shape, dtype=np.float64)
    infiltration = np.zeros(shape, dtype=np.float64)
    drainage = np.zeros(shape, dtype=np.float64)
    terrain = np.empty(shape, dtype="U16")
    building = np.full(shape, "", dtype="U64")
    district = np.empty(shape, dtype="U32")
    road = np.zeros(shape, dtype=np.bool_)
    flow = np.zeros(shape, dtype=np.bool_)
    inlet = np.zeros(shape, dtype=np.bool_)
    seen = np.zeros(shape, dtype=np.bool_)

    for cell in cells:
        x, y = int(cell["x"]), int(cell["y"])
        if not (0 <= x < width and 0 <= y < height) or seen[y, x]:
            raise ValueError(f"Invalid or duplicate Eastbank coordinate ({x}, {y})")
        seen[y, x] = True
        terrain_type = str(cell["terrain_type"])
        building_id = cell.get("building_id") or ""
        elevation[y, x] = float(cell["elevation_mm"])
        impervious[y, x] = float(cell["impervious_ratio"])
        infiltration[y, x] = float(cell["infiltration_rate_mm_hr"])
        drainage[y, x] = float(cell["drainage_capacity_mm_hr"])
        terrain[y, x] = terrain_type
        building[y, x] = str(building_id)
        district[y, x] = str(cell["district_id"])
        road[y, x] = bool(cell.get("is_road", terrain_type == "road"))
        flow[y, x] = bool(cell["can_water_flow"])
        inlet[y, x] = str(cell.get("interactive_object_id", "")).startswith("drain-")

    if not np.all(seen):
        raise ValueError("Eastbank map contains missing grid coordinates")
    if np.any((impervious < 0) | (impervious > 1)):
        raise ValueError("impervious_ratio must be within [0, 1]")
    if np.any(elevation < 0) or np.any(infiltration < 0) or np.any(drainage < 0):
        raise ValueError("Elevation and capacity fields cannot be negative")

    cell_type = np.full(shape, "land", dtype="U16")
    cell_type[terrain == "road"] = "road"
    cell_type[terrain == "river"] = "river"
    cell_type[terrain == "canal"] = "waterway"
    cell_type[building != ""] = "obstacle"
    grid = SimulationGrid(
        width=width, height=height, cell_size_m=float(tile_px),
        elevation_mm=elevation, impervious_ratio=impervious,
        infiltration_rate_mm_hr=infiltration, drainage_capacity_mm_hr=drainage,
        terrain_type=terrain, cell_type=cell_type, building_id=building,
        district_id=district, is_road=road, can_water_flow=flow,
        is_drain_inlet=inlet, water_depth_mm=np.zeros(shape, dtype=np.float64),
    )
    return grid, document
