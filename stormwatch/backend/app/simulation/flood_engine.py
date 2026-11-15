"""Deterministic NumPy flood engine with independent, session-owned instances."""
from __future__ import annotations

from pathlib import Path
from threading import RLock

import numpy as np

from app.simulation.drainage import DrainageFlux, apply_drainage, apply_rainfall
from app.simulation.grid import load_grid
from app.simulation.resources import Direction, Position, ResourceInventory
from app.simulation.state import SimulationState
from app.simulation.water_flow import advance_water_flow

DT_HOURS = 1.0 / 6.0
DEFAULT_SEED = 2406


def _new_state(seed: int = DEFAULT_SEED, grid_path: str | Path | None = None) -> SimulationState:
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be an integer between 0 and 4294967295")
    grid, document = load_grid(grid_path)
    state = SimulationState(
        grid=grid,
        map_document=document,
        seed=int(seed),
        rainfall_intensity_mm_hr=np.zeros((grid.height, grid.width), dtype=np.float64),
        resources=ResourceInventory(),
        dt_hours=DT_HOURS,
    )
    state.initial_volume_mm_cells = float(np.sum(grid.water_depth_mm, dtype=np.float64))
    return state


class FloodEngine:
    """An isolated flood simulation; each game session owns one instance."""

    def __init__(self, seed: int = DEFAULT_SEED, grid_path: str | Path | None = None) -> None:
        self._lock = RLock()
        self._grid_path = grid_path
        self._state = _new_state(seed, grid_path)

    @property
    def seed(self) -> int:
        return self._state.seed

    def set_rainfall(self, rainfall_intensity_mm_hr: float | np.ndarray) -> dict:
        """Set a uniform rainfall rate or a height×width intensity grid."""
        with self._lock:
            state = self._state
            rainfall = np.asarray(rainfall_intensity_mm_hr, dtype=np.float64)
            if not np.all(np.isfinite(rainfall)) or np.any(rainfall < 0) or np.any(rainfall > 500):
                raise ValueError("Rainfall intensity must be finite and within 0..500 mm/hour")
            if rainfall.ndim == 0:
                state.rainfall_intensity_mm_hr[:] = float(rainfall)
            elif rainfall.shape == state.rainfall_intensity_mm_hr.shape:
                state.rainfall_intensity_mm_hr[:] = rainfall
            else:
                raise ValueError(f"Rainfall grid must have shape {state.rainfall_intensity_mm_hr.shape}")
            return state.to_dict()

    def advance(self, steps: int = 1) -> dict:
        """Advance one or more ten-minute timesteps in small bounded batches."""
        if not isinstance(steps, int) or isinstance(steps, bool) or steps < 1 or steps > 144:
            raise ValueError("steps must be an integer between 1 and 144")
        with self._lock:
            state = self._state
            grid = state.grid
            for _ in range(steps):
                rainfall_flux = apply_rainfall(grid, state.rainfall_intensity_mm_hr, state.dt_hours)
                drainage_flux = apply_drainage(
                    grid, state.resources, state.dt_hours,
                    pump_attenuation_power=state.pump_attenuation_power,
                )
                flow = advance_water_flow(
                    grid,
                    state.resources.barrier_crests_mm(grid),
                    max_transfer_fraction=state.max_transfer_fraction,
                    flow_coefficient=state.flow_coefficient,
                )
                grid.water_depth_mm[:] = flow.water_depth_mm
                state.balance.add_rain_and_drainage(DrainageFlux(
                    precipitation_mm_cells=rainfall_flux.precipitation_mm_cells,
                    surface_input_mm_cells=rainfall_flux.surface_input_mm_cells,
                    infiltration_mm_cells=rainfall_flux.infiltration_mm_cells,
                    natural_drainage_mm_cells=drainage_flux.natural_drainage_mm_cells,
                    installed_drainage_mm_cells=drainage_flux.installed_drainage_mm_cells,
                    pump_removal_mm_cells=drainage_flux.pump_removal_mm_cells,
                ))
                state.balance.boundary_outflow_mm_cells += flow.boundary_outflow_mm_cells
                state.balance.internal_transfer_mm_cells += flow.internal_transfer_mm_cells
                state.timestep_index += 1
            return state.to_dict()

    def place_barrier(
        self,
        position: Position,
        direction: Direction,
        barrier_height_mm: float = 300.0,
        deployment_cost: int = 850,
    ) -> dict:
        with self._lock:
            state = self._state
            state.resources.place_barrier(state.grid, position, direction, barrier_height_mm, deployment_cost)
            return state.to_dict()

    def place_pump(
        self,
        grid_position: Position,
        drainage_capacity_mm_hr: float = 40.0,
        operating_radius_cells: float = 2.5,
        deployment_cost: int = 4_500,
    ) -> dict:
        with self._lock:
            state = self._state
            state.resources.place_pump(
                state.grid, grid_position, drainage_capacity_mm_hr,
                operating_radius_cells, deployment_cost,
            )
            return state.to_dict()

    def place_rescue_boat(self, grid_position: Position, deployment_cost: int = 3_200) -> dict:
        with self._lock:
            state = self._state
            state.resources.place_rescue_boat(state.grid, grid_position, deployment_cost)
            return state.to_dict()

    def get_state(self) -> dict:
        with self._lock:
            return self._state.to_dict()

    def reset(self, seed: int | None = None) -> dict:
        with self._lock:
            next_seed = self._state.seed if seed is None else seed
            self._state = _new_state(next_seed, self._grid_path)
            return self._state.to_dict()


_default_engine_lock = RLock()
_default_engine: FloodEngine | None = None


def _require_default_engine() -> FloodEngine:
    global _default_engine
    with _default_engine_lock:
        if _default_engine is None:
            _default_engine = FloodEngine()
        return _default_engine


# Backwards-compatible singleton helpers remain for the earlier prototype API/tests.
def initialize_simulation(seed: int = DEFAULT_SEED, grid_path: str | Path | None = None) -> dict:
    global _default_engine
    with _default_engine_lock:
        _default_engine = FloodEngine(seed, grid_path)
        return _default_engine.get_state()


def set_rainfall(rainfall_intensity_mm_hr: float | np.ndarray) -> dict:
    return _require_default_engine().set_rainfall(rainfall_intensity_mm_hr)


def advance_simulation(steps: int = 1) -> dict:
    return _require_default_engine().advance(steps)


def place_barrier(position: Position, direction: Direction, barrier_height_mm: float = 300.0,
                  deployment_cost: int = 850) -> dict:
    return _require_default_engine().place_barrier(position, direction, barrier_height_mm, deployment_cost)


def place_pump(grid_position: Position, drainage_capacity_mm_hr: float = 40.0,
               operating_radius_cells: float = 2.5, deployment_cost: int = 4_500) -> dict:
    return _require_default_engine().place_pump(
        grid_position, drainage_capacity_mm_hr, operating_radius_cells, deployment_cost,
    )


def place_rescue_boat(grid_position: Position, deployment_cost: int = 3_200) -> dict:
    return _require_default_engine().place_rescue_boat(grid_position, deployment_cost)


def get_simulation_state() -> dict:
    return _require_default_engine().get_state()


def reset_simulation(seed: int | None = None) -> dict:
    return _require_default_engine().reset(seed)
