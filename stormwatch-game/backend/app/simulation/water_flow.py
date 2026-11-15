"""Order-independent, two-stage four-neighbour surface water transfer."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.simulation.grid import SimulationGrid
from app.simulation.resources import EdgeKey


@dataclass(frozen=True)
class FlowResult:
    water_depth_mm: NDArray[np.float64]
    internal_transfer_mm_cells: float
    boundary_outflow_mm_cells: float


def _barrier_crest_arrays(grid: SimulationGrid, crests: dict[EdgeKey, float]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    horizontal = np.full((grid.height, max(0, grid.width - 1)), -np.inf, dtype=np.float64)
    vertical = np.full((max(0, grid.height - 1), grid.width), -np.inf, dtype=np.float64)
    for x, y, nx, ny in crests:
        if y == ny and abs(nx - x) == 1:
            horizontal[y, min(x, nx)] = crests[(x, y, nx, ny)]
        elif x == nx and abs(ny - y) == 1:
            vertical[min(y, ny), x] = crests[(x, y, nx, ny)]
    return horizontal, vertical


def advance_water_flow(grid: SimulationGrid, barriers: dict[EdgeKey, float],
                       max_transfer_fraction: float = 0.25,
                       flow_coefficient: float = 0.25,
                       sea_level_mm: float = 0.0) -> FlowResult:
    """Transfer water downhill from the timestep snapshot, then apply one buffer.

    Each edge contributes a potential transfer based on the starting water
    surfaces. Per-cell scaling caps total outflow, while a separate delta array
    applies all inflows/outflows simultaneously. Buildings block both directions.
    """
    if not 0.0 < max_transfer_fraction <= 1.0:
        raise ValueError("max_transfer_fraction must be in (0, 1]")
    if not 0.0 < flow_coefficient <= 0.5:
        raise ValueError("flow_coefficient must be in (0, 0.5]")

    depth = np.maximum(grid.water_depth_mm, 0.0)
    surface = grid.elevation_mm + depth
    passable = grid.flow_mask
    crest_h, crest_v = _barrier_crest_arrays(grid, barriers)
    outgoing = np.zeros_like(depth)
    edge_potentials: list[tuple[str, NDArray[np.float64], NDArray[np.float64]]] = []

    # East-west cell edges.
    left_surface, right_surface = surface[:, :-1], surface[:, 1:]
    left_to_right = (left_surface > right_surface) & passable[:, :-1] & passable[:, 1:] & (left_surface > crest_h)
    right_to_left = (right_surface > left_surface) & passable[:, :-1] & passable[:, 1:] & (right_surface > crest_h)
    pot_lr = np.where(left_to_right, (left_surface - right_surface) * flow_coefficient, 0.0)
    pot_rl = np.where(right_to_left, (right_surface - left_surface) * flow_coefficient, 0.0)
    outgoing[:, :-1] += pot_lr; outgoing[:, 1:] += pot_rl
    edge_potentials.append(("h", pot_lr, pot_rl))

    # North-south cell edges.
    north_surface, south_surface = surface[:-1, :], surface[1:, :]
    north_to_south = (north_surface > south_surface) & passable[:-1, :] & passable[1:, :] & (north_surface > crest_v)
    south_to_north = (south_surface > north_surface) & passable[:-1, :] & passable[1:, :] & (south_surface > crest_v)
    pot_ns = np.where(north_to_south, (north_surface - south_surface) * flow_coefficient, 0.0)
    pot_sn = np.where(south_to_north, (south_surface - north_surface) * flow_coefficient, 0.0)
    outgoing[:-1, :] += pot_ns; outgoing[1:, :] += pot_sn
    edge_potentials.append(("v", pot_ns, pot_sn))

    # The west edge is an open sea boundary only where the river reaches x=0.
    boundary_mask = grid.terrain_type[:, 0] == "river"
    boundary_potential = np.where(
        boundary_mask,
        np.maximum(0.0, surface[:, 0] - sea_level_mm) * flow_coefficient,
        0.0,
    )
    outgoing[:, 0] += boundary_potential
    scale = np.divide(
        np.minimum(depth * max_transfer_fraction, outgoing), outgoing,
        out=np.zeros_like(depth), where=outgoing > 0,
    )

    # Stage two: accumulate equal and opposite transfers, then update once.
    delta = np.zeros_like(depth)
    internal_total = 0.0
    for orientation, forward, reverse in edge_potentials:
        if orientation == "h":
            f = forward * scale[:, :-1]
            r = reverse * scale[:, 1:]
            delta[:, :-1] -= f; delta[:, 1:] += f
            delta[:, 1:] -= r; delta[:, :-1] += r
        else:
            f = forward * scale[:-1, :]
            r = reverse * scale[1:, :]
            delta[:-1, :] -= f; delta[1:, :] += f
            delta[1:, :] -= r; delta[:-1, :] += r
        internal_total += float(np.sum(f, dtype=np.float64) + np.sum(r, dtype=np.float64))

    boundary_outflow = boundary_potential * scale[:, 0]
    delta[:, 0] -= boundary_outflow
    updated = depth + delta
    # This clamp only removes floating-point underflow; source outflow was capped above.
    updated = np.maximum(updated, 0.0)
    return FlowResult(updated, internal_total, float(np.sum(boundary_outflow, dtype=np.float64)))
