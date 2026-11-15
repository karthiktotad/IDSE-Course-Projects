"""Player-placed flood response resources and edge barrier geometry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from app.simulation.grid import SimulationGrid

Direction = Literal["N", "E", "S", "W"]
Position = tuple[int, int]
EdgeKey = tuple[int, int, int, int]


def neighbor(position: Position, direction: Direction) -> Position:
    x, y = position
    return {"N": (x, y - 1), "E": (x + 1, y), "S": (x, y + 1), "W": (x - 1, y)}[direction]


def edge_key(a: Position, b: Position) -> EdgeKey:
    first, second = sorted((a, b), key=lambda point: (point[1], point[0]))
    return first[0], first[1], second[0], second[1]


@dataclass(frozen=True)
class FloodBarrier:
    position: Position
    direction: Direction
    height_mm: float
    deployment_cost: int

    @property
    def adjacent_position(self) -> Position:
        return neighbor(self.position, self.direction)

    def to_dict(self) -> dict:
        return {"position": {"x": self.position[0], "y": self.position[1]},
                "direction": self.direction, "height_mm": self.height_mm,
                "deployment_cost": self.deployment_cost}


@dataclass(frozen=True)
class WaterPump:
    grid_position: Position
    drainage_capacity_mm_hr: float
    operating_radius_cells: float
    deployment_cost: int

    def to_dict(self) -> dict:
        return {"grid_position": {"x": self.grid_position[0], "y": self.grid_position[1]},
                "drainage_capacity_mm_hr": self.drainage_capacity_mm_hr,
                "operating_radius_cells": self.operating_radius_cells,
                "deployment_cost": self.deployment_cost}


@dataclass(frozen=True)
class RescueBoat:
    grid_position: Position
    deployment_cost: int = 35
    operating_radius_cells: float = 5.0
    evacuation_capacity: int = 30

    def to_dict(self) -> dict:
        return {"grid_position": {"x": self.grid_position[0], "y": self.grid_position[1]},
                "deployment_cost": self.deployment_cost,
                "operating_radius_cells": self.operating_radius_cells,
                "evacuation_capacity": self.evacuation_capacity}


class ResourceInventory:
    """Small deterministic inventory and budget used by the local prototype."""
    def __init__(self, budget_credits: int = 100, barriers: int = 1,
                 pumps: int = 1, rescue_boats: int = 1) -> None:
        self.initial_budget = budget_credits
        self.budget_remaining = budget_credits
        self.barriers_remaining = barriers
        self.pumps_remaining = pumps
        self.rescue_boats_remaining = rescue_boats
        self.barriers: list[FloodBarrier] = []
        self.pumps: list[WaterPump] = []
        self.rescue_boats: list[RescueBoat] = []

    def charge(self, cost: int) -> None:
        if cost < 0:
            raise ValueError("Deployment cost cannot be negative")
        if cost > self.budget_remaining:
            raise ValueError("Insufficient response budget")
        self.budget_remaining -= cost

    def place_barrier(self, grid: SimulationGrid, position: Position,
                      direction: Direction, height_mm: float,
                      deployment_cost: int = 25) -> FloodBarrier:
        if direction not in {"N", "E", "S", "W"}:
            raise ValueError("Barrier direction must be N, E, S or W")
        x, y = position
        nx, ny = neighbor(position, direction)
        if not (0 <= x < grid.width and 0 <= y < grid.height and 0 <= nx < grid.width and 0 <= ny < grid.height):
            raise ValueError("A barrier edge must join two in-bounds adjacent cells")
        if height_mm <= 0:
            raise ValueError("Barrier height must be greater than zero")
        if self.barriers_remaining <= 0:
            raise ValueError("No flood barriers remain")
        key = edge_key(position, (nx, ny))
        if any(edge_key(item.position, item.adjacent_position) == key for item in self.barriers):
            raise ValueError("A barrier already occupies this cell edge")
        barrier = FloodBarrier(position, direction, float(height_mm), int(deployment_cost))
        self.charge(barrier.deployment_cost)
        self.barriers_remaining -= 1
        self.barriers.append(barrier)
        return barrier

    def place_pump(self, grid: SimulationGrid, grid_position: Position,
                   drainage_capacity_mm_hr: float = 40.0,
                   operating_radius_cells: float = 2.5,
                   deployment_cost: int = 40) -> WaterPump:
        x, y = grid_position
        if not (0 <= x < grid.width and 0 <= y < grid.height):
            raise ValueError("Pump grid position is outside Eastbank")
        if grid.cell_type[y, x] == "obstacle":
            raise ValueError("Pumps cannot be placed inside buildings")
        if grid.terrain_type[y, x] not in {"grass", "park", "road"} or not grid.can_water_flow[y, x]:
            raise ValueError("Pumps require an accessible open-ground or road cell")
        if drainage_capacity_mm_hr <= 0 or operating_radius_cells <= 0:
            raise ValueError("Pump capacity and operating radius must be positive")
        if self.pumps_remaining <= 0:
            raise ValueError("No water pumps remain")
        pump = WaterPump(grid_position, float(drainage_capacity_mm_hr),
                         float(operating_radius_cells), int(deployment_cost))
        self.charge(pump.deployment_cost)
        self.pumps_remaining -= 1
        self.pumps.append(pump)
        return pump

    def place_rescue_boat(self, grid: SimulationGrid, grid_position: Position,
                          deployment_cost: int = 35) -> RescueBoat:
        x, y = grid_position
        if not (0 <= x < grid.width and 0 <= y < grid.height):
            raise ValueError("Rescue boat grid position is outside Eastbank")
        if grid.terrain_type[y, x] not in {"river", "canal"} and not grid.is_road[y, x]:
            raise ValueError("Rescue boats must be placed at a road, river or drainage-canal access point")
        if self.rescue_boats_remaining <= 0:
            raise ValueError("No rescue boats remain")
        boat = RescueBoat(grid_position, int(deployment_cost))
        self.charge(boat.deployment_cost)
        self.rescue_boats_remaining -= 1
        self.rescue_boats.append(boat)
        return boat

    def barrier_crests_mm(self, grid: SimulationGrid) -> dict[EdgeKey, float]:
        crests: dict[EdgeKey, float] = {}
        for barrier in self.barriers:
            a, b = barrier.position, barrier.adjacent_position
            ax, ay = a; bx, by = b
            ground = max(grid.elevation_mm[ay, ax], grid.elevation_mm[by, bx])
            crests[edge_key(a, b)] = float(ground + barrier.height_mm)
        return crests

    def pump_capacity_grid(self, grid: SimulationGrid,
                           attenuation_power: float = 2.0) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
        capacity = np.zeros((grid.height, grid.width), dtype=np.float64)
        yy, xx = np.mgrid[0:grid.height, 0:grid.width]
        for pump in self.pumps:
            px, py = pump.grid_position
            distance = np.sqrt((xx - px) ** 2 + (yy - py) ** 2)
            attenuation = np.clip(1.0 - distance / pump.operating_radius_cells, 0.0, 1.0) ** attenuation_power
            capacity += pump.drainage_capacity_mm_hr * attenuation
        return capacity, grid.flow_mask

    def to_dict(self) -> dict:
        return {
            "budget_initial_credits": self.initial_budget,
            "budget_remaining_credits": self.budget_remaining,
            "inventory": {"barriers": self.barriers_remaining, "pumps": self.pumps_remaining,
                          "rescue_boats": self.rescue_boats_remaining},
            "barriers": [item.to_dict() for item in self.barriers],
            "pumps": [item.to_dict() for item in self.pumps],
            "rescue_boats": [item.to_dict() for item in self.rescue_boats],
        }
