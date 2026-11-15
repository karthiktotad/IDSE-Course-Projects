"""Mutable state and serializable summaries for one Eastbank run."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from app.simulation.drainage import DrainageFlux
from app.simulation.grid import SimulationGrid
from app.simulation.resources import ResourceInventory


@dataclass
class CumulativeBalance:
    precipitation_mm_cells: float = 0.0
    surface_input_mm_cells: float = 0.0
    infiltration_mm_cells: float = 0.0
    natural_drainage_mm_cells: float = 0.0
    installed_drainage_mm_cells: float = 0.0
    pump_removal_mm_cells: float = 0.0
    boundary_outflow_mm_cells: float = 0.0
    internal_transfer_mm_cells: float = 0.0

    def add_rain_and_drainage(self, flux: DrainageFlux) -> None:
        self.precipitation_mm_cells += flux.precipitation_mm_cells
        self.surface_input_mm_cells += flux.surface_input_mm_cells
        self.infiltration_mm_cells += flux.infiltration_mm_cells
        self.natural_drainage_mm_cells += flux.natural_drainage_mm_cells
        self.installed_drainage_mm_cells += flux.installed_drainage_mm_cells
        self.pump_removal_mm_cells += flux.pump_removal_mm_cells

    @property
    def drainage_mm_cells(self) -> float:
        return self.natural_drainage_mm_cells + self.installed_drainage_mm_cells + self.pump_removal_mm_cells


@dataclass
class SimulationState:
    grid: SimulationGrid
    map_document: dict
    seed: int
    rainfall_intensity_mm_hr: NDArray[np.float64]
    resources: ResourceInventory = field(default_factory=ResourceInventory)
    timestep_index: int = 0
    dt_hours: float = 1.0 / 6.0
    max_transfer_fraction: float = 0.25
    flow_coefficient: float = 0.25
    pump_attenuation_power: float = 2.0
    flooded_cell_threshold_mm: float = 1.0
    road_passability_depth_mm: float = 50.0
    balance: CumulativeBalance = field(default_factory=CumulativeBalance)
    initial_volume_mm_cells: float = 0.0

    @property
    def elapsed_minutes(self) -> int:
        return self.timestep_index * 10

    @property
    def elapsed_seconds(self) -> int:
        return self.timestep_index * 600

    def _location_access_status(self, location: dict) -> str:
        x0, y0 = location["x"], location["y"]
        x1, y1 = x0 + location["width"] - 1, y0 + location["height"] - 1
        road_open = self.grid.is_road & (self.grid.water_depth_mm < self.road_passability_depth_mm)
        starts: set[tuple[int, int]] = set()
        for x in range(x0, x1 + 1):
            for y in (y0 - 1, y1 + 1):
                if 0 <= y < self.grid.height and road_open[y, x]: starts.add((x, y))
        for y in range(y0, y1 + 1):
            for x in (x0 - 1, x1 + 1):
                if 0 <= x < self.grid.width and road_open[y, x]: starts.add((x, y))
        if not starts:
            return "inaccessible"
        seen = set(starts)
        frontier = list(starts)
        while frontier:
            x, y = frontier.pop()
            if x in (0, self.grid.width - 1) or y in (0, self.grid.height - 1):
                return "accessible"
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < self.grid.width and 0 <= ny < self.grid.height and (nx, ny) not in seen and road_open[ny, nx]:
                    seen.add((nx, ny)); frontier.append((nx, ny))
        return "inaccessible"

    def location_accessibility_status(self) -> dict[str, str]:
        """Report road-network reachability for the hospital and school."""
        critical = {"hospital", "school"}
        return {
            place["id"]: self._location_access_status(place)
            for place in self.map_document["locations"]
            if place["kind"] in critical
        }

    def hospital_access_status(self) -> str:
        hospital = next((p for p in self.map_document["locations"] if p["kind"] == "hospital"), None)
        return self._location_access_status(hospital) if hospital else "unknown"

    def flood_risk_index(self) -> NDArray[np.float64]:
        depth = self.grid.water_depth_mm
        low_ground = np.clip((2200.0 - self.grid.elevation_mm) / 2200.0, 0.0, 1.0)
        rain_exposure = np.clip(self.rainfall_intensity_mm_hr / 60.0, 0.0, 1.0)
        depth_exposure = np.clip(depth / 100.0, 0.0, 1.0)
        risk = 100.0 * (0.56 * depth_exposure + 0.20 * low_ground + 0.14 * rain_exposure + 0.10 * self.grid.impervious_ratio)
        risk[self.grid.cell_type == "obstacle"] *= 0.85
        return np.clip(risk, 0.0, 100.0)

    def volume_balance(self) -> dict:
        factor = self.grid.cell_area_m2 / 1000.0
        initial = self.initial_volume_mm_cells * factor
        rain = self.balance.precipitation_mm_cells * factor
        infiltration = self.balance.infiltration_mm_cells * factor
        natural = self.balance.natural_drainage_mm_cells * factor
        installed = self.balance.installed_drainage_mm_cells * factor
        pumps = self.balance.pump_removal_mm_cells * factor
        boundary = self.balance.boundary_outflow_mm_cells * factor
        final = self.grid.volume_m3()
        error = initial + rain - infiltration - natural - installed - pumps - boundary - final
        return {
            "unit": "m3",
            "initial_water_m3": initial,
            "cumulative_rainfall_m3": rain,
            "surface_rainfall_input_m3": self.balance.surface_input_mm_cells * factor,
            "infiltration_m3": infiltration,
            "natural_drainage_m3": natural,
            "installed_drainage_m3": installed,
            "pump_removal_m3": pumps,
            "total_drainage_m3": natural + installed + pumps,
            "boundary_outflow_m3": boundary,
            "final_water_m3": final,
            "balance_error_m3": error,
            "balanced": abs(error) <= max(1e-7, (initial + rain) * 1e-10),
            "internal_transfers_m3_moved": self.balance.internal_transfer_mm_cells * factor,
        }

    def to_dict(self) -> dict:
        grid = self.grid
        depth = grid.water_depth_mm
        risk = self.flood_risk_index()
        flooded = depth >= self.flooded_cell_threshold_mm
        flooded_cells = [
            {"x": int(x), "y": int(y), "water_depth_mm": round(float(depth[y, x]), 3)}
            for y, x in zip(*np.nonzero(flooded))
        ]
        cells = []
        for y in range(grid.height):
            for x in range(grid.width):
                cells.append({
                    "x": x, "y": y,
                    "terrain_type": str(grid.terrain_type[y, x]),
                    "cell_type": str(grid.cell_type[y, x]),
                    "elevation_mm": float(grid.elevation_mm[y, x]),
                    "water_depth_mm": round(float(depth[y, x]), 3),
                    "impervious_ratio": float(grid.impervious_ratio[y, x]),
                    "infiltration_rate_mm_hr": float(grid.infiltration_rate_mm_hr[y, x]),
                    "drainage_capacity_mm_hr": float(grid.drainage_capacity_mm_hr[y, x]),
                    "rainfall_intensity_mm_hr": float(self.rainfall_intensity_mm_hr[y, x]),
                    "flood_risk_index": round(float(risk[y, x]), 2),
                    "building_id": str(grid.building_id[y, x]) or None,
                    "district_id": str(grid.district_id[y, x]),
                    "can_water_flow": bool(grid.can_water_flow[y, x]),
                    "is_road": bool(grid.is_road[y, x]),
                    "is_drain_inlet": bool(grid.is_drain_inlet[y, x]),
                })
        return {
            "map_id": self.map_document["map_id"],
            "name": self.map_document["name"],
            "columns": grid.width, "rows": grid.height,
            "tile_size_px": self.map_document["tile_size_px"],
            "pixel_width": self.map_document["pixel_width"],
            "pixel_height": self.map_document["pixel_height"],
            "seed": self.seed,
            "timestep_minutes": 10,
            "dt_hours": self.dt_hours,
            "flow_configuration": {
                "max_transfer_fraction_per_timestep": self.max_transfer_fraction,
                "flow_coefficient": self.flow_coefficient,
                "pump_attenuation_power": self.pump_attenuation_power,
                "flooded_cell_threshold_mm": self.flooded_cell_threshold_mm,
                "road_passability_depth_mm": self.road_passability_depth_mm,
            },
            "elapsed_minutes": self.elapsed_minutes,
            "elapsed_seconds": self.elapsed_seconds,
            "rainfall_mm_per_hour": float(np.mean(self.rainfall_intensity_mm_hr)),
            "water_depth_grid_mm": np.round(depth, 3).tolist(),
            "cells": cells,
            "flooded_cells": flooded_cells,
            "total_flooded_cells": len(flooded_cells),
            "maximum_water_depth_mm": float(np.max(depth)),
            "average_water_depth_mm": float(np.mean(depth)),
            "flooded_road_count": int(np.count_nonzero(flooded & grid.is_road)),
            "hospital_access_status": self.hospital_access_status(),
            "location_accessibility": self.location_accessibility_status(),
            "water_volume_balance": self.volume_balance(),
            "resources": self.resources.to_dict(),
        }
