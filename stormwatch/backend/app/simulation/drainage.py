"""Rainfall partition, infiltration, drainage and pump removal."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.simulation.grid import SimulationGrid
from app.simulation.resources import ResourceInventory


@dataclass(frozen=True)
class DrainageFlux:
    precipitation_mm_cells: float = 0.0
    surface_input_mm_cells: float = 0.0
    infiltration_mm_cells: float = 0.0
    natural_drainage_mm_cells: float = 0.0
    installed_drainage_mm_cells: float = 0.0
    pump_removal_mm_cells: float = 0.0

    @property
    def total_drainage_mm_cells(self) -> float:
        return self.natural_drainage_mm_cells + self.installed_drainage_mm_cells + self.pump_removal_mm_cells


def runoff_fraction(impervious_ratio: NDArray[np.float64]) -> NDArray[np.float64]:
    """A simple educational coefficient: 0.20 on permeable ground, 0.95 when sealed."""
    return np.clip(0.20 + 0.75 * impervious_ratio, 0.0, 1.0)


def _route_roof_runoff(grid: SimulationGrid, surface_input: NDArray[np.float64]) -> NDArray[np.float64]:
    """Send roof runoff to adjacent passable cells; enclosed roofs retain it locally."""
    obstacles = grid.cell_type == "obstacle"
    passable = grid.flow_mask
    routed = np.where(passable, surface_input, 0.0)
    roof = np.where(obstacles, surface_input, 0.0)
    count = np.zeros((grid.height, grid.width), dtype=np.float64)

    # Count each eligible four-way neighbour of an obstacle roof cell.
    count[:, :-1] += (obstacles[:, 1:] & passable[:, :-1])
    count[:, 1:] += (obstacles[:, :-1] & passable[:, 1:])
    count[:-1, :] += (obstacles[1:, :] & passable[:-1, :])
    count[1:, :] += (obstacles[:-1, :] & passable[1:, :])

    for source, target in (
        ((slice(None), slice(1, None)), (slice(None), slice(None, -1))),
        ((slice(None), slice(None, -1)), (slice(None), slice(1, None))),
        ((slice(1, None), slice(None)), (slice(None, -1), slice(None))),
        ((slice(None, -1), slice(None)), (slice(1, None), slice(None))),
    ):
        source_roof = roof[source]
        target_open = passable[target]
        target_count = count[source]
        share = np.divide(source_roof, target_count, out=np.zeros_like(source_roof), where=target_count > 0)
        routed[target] += np.where(target_open & obstacles[source], share, 0.0)

    enclosed = obstacles & (count == 0)
    routed[enclosed] = surface_input[enclosed]
    return routed


def apply_rainfall(grid: SimulationGrid, rainfall_intensity_mm_hr: NDArray[np.float64],
                   dt_hours: float) -> DrainageFlux:
    """Partition one timestep of precipitation into surface runoff and infiltration.

    Any pervious rainfall that exceeds the cell's infiltration capacity becomes
    excess surface runoff. Thus precipitation is conserved in every cell before
    local roof runoff routing.
    """
    gross_rain = np.maximum(rainfall_intensity_mm_hr, 0.0) * dt_hours
    fraction = runoff_fraction(grid.impervious_ratio)
    rainfall_input = gross_rain * fraction
    remaining_rainfall = gross_rain - rainfall_input
    infiltration_capacity = grid.infiltration_rate_mm_hr * dt_hours * (1.0 - grid.impervious_ratio)
    infiltration = np.minimum(remaining_rainfall, infiltration_capacity)
    excess_runoff = remaining_rainfall - infiltration
    surface_input = rainfall_input + excess_runoff
    grid.water_depth_mm += _route_roof_runoff(grid, surface_input)
    return DrainageFlux(
        precipitation_mm_cells=float(np.sum(gross_rain, dtype=np.float64)),
        surface_input_mm_cells=float(np.sum(surface_input, dtype=np.float64)),
        infiltration_mm_cells=float(np.sum(infiltration, dtype=np.float64)),
    )


def apply_drainage(grid: SimulationGrid, resources: ResourceInventory,
                   dt_hours: float, natural_capacity_cap_mm_hr: float = 2.0,
                   pump_attenuation_power: float = 2.0) -> DrainageFlux:
    """Remove water by natural drainage, fixed inlets, then placed pumps."""
    available = np.maximum(grid.water_depth_mm, 0.0)
    ordinary_ground = grid.flow_mask & ~grid.waterway_mask
    natural_rate = np.where(
        ordinary_ground,
        np.minimum(grid.drainage_capacity_mm_hr, natural_capacity_cap_mm_hr),
        0.0,
    )
    natural_removed = np.minimum(available, natural_rate * dt_hours)
    available -= natural_removed

    installed_rate = np.where(grid.is_drain_inlet & ordinary_ground,
                              grid.drainage_capacity_mm_hr, 0.0)
    installed_removed = np.minimum(available, installed_rate * dt_hours)
    available -= installed_removed

    pump_rate, eligible = resources.pump_capacity_grid(grid, pump_attenuation_power)
    pump_removed = np.minimum(available, np.where(eligible, pump_rate * dt_hours, 0.0))
    available -= pump_removed
    grid.water_depth_mm[:] = np.maximum(available, 0.0)
    return DrainageFlux(
        natural_drainage_mm_cells=float(np.sum(natural_removed, dtype=np.float64)),
        installed_drainage_mm_cells=float(np.sum(installed_removed, dtype=np.float64)),
        pump_removal_mm_cells=float(np.sum(pump_removed, dtype=np.float64)),
    )
