"""Seeded weather and water observations generated through the Eastbank model.

Atmospheric features use a few changing synthetic storm regimes. Rainfall is
spatially interpolated from the four mapped gauges, then passed through the
same NumPy flood, infiltration and drainage engine used by gameplay. This
keeps observed water depth physically connected to the simulation inputs.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.simulation.drainage import DrainageFlux, apply_drainage, apply_rainfall
from app.simulation.grid import SimulationGrid, load_grid
from app.simulation.resources import ResourceInventory
from app.simulation.state import SimulationState
from app.simulation.water_flow import advance_water_flow

DEFAULT_SEED = 2406
DEFAULT_EVENT_COUNT = 4
DEFAULT_STEPS_PER_EVENT = 36
DEFAULT_SCENARIO_STEPS = 144
TIMESTEP_MINUTES = 10
_DATA_START = datetime(2026, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class WeatherObservation:
    timestamp: str
    station_id: str
    rainfall_mm_hr: float
    temperature_c: float
    humidity_pct: float
    wind_speed_kmh: float
    pressure_hpa: float
    water_depth_mm: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WeatherStation:
    station_id: str
    name: str
    x: int
    y: int

    def to_dict(self) -> dict[str, Any]:
        return {"station_id": self.station_id, "name": self.name, "x": self.x, "y": self.y}


@dataclass(frozen=True)
class WeatherDataset:
    seed: int
    historical: tuple[WeatherObservation, ...]
    eastbank_scenario: tuple[WeatherObservation, ...]
    stations: tuple[WeatherStation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "stations": [station.to_dict() for station in self.stations],
            "historical": [record.to_dict() for record in self.historical],
            "eastbank_scenario": [record.to_dict() for record in self.eastbank_scenario],
        }


def _eastbank_path() -> Path:
    return Path(__file__).resolve().parents[3] / "shared" / "eastbank_grid.json"


def _load_stations(document: dict[str, Any]) -> tuple[WeatherStation, ...]:
    stations = tuple(
        WeatherStation(
            station_id=str(location["id"]),
            name=str(location["name"]),
            x=int(location["x"]),
            y=int(location["y"]),
        )
        for location in document.get("locations", [])
        if location.get("kind") == "weather_station"
    )
    if len(stations) < 2:
        raise ValueError("Eastbank must define at least two weather monitoring stations")
    if len({station.station_id for station in stations}) != len(stations):
        raise ValueError("Weather station identifiers must be unique")
    return stations


def _interpolation_weights(grid: SimulationGrid, stations: tuple[WeatherStation, ...]) -> NDArray[np.float64]:
    yy, xx = np.mgrid[0:grid.height, 0:grid.width]
    distances_squared = np.stack(
        [(xx - station.x) ** 2 + (yy - station.y) ** 2 for station in stations], axis=0
    ).astype(np.float64)
    # A small distance floor prevents a gauge cell from receiving infinite weight.
    weights = 1.0 / np.maximum(distances_squared, 1.0)
    return weights / np.sum(weights, axis=0, keepdims=True)


def _event_rainfall(
    rng: np.random.Generator,
    event_index: int,
    steps: int,
    station_count: int,
    scenario: bool,
) -> NDArray[np.float64]:
    progress = np.linspace(0.0, 1.0, steps, dtype=np.float64)
    if scenario:
        # The new watch contains a broad first pulse and a sharper coastal band.
        pulse = 0.68 * np.sin(np.pi * progress) ** 1.4
        pulse += 0.54 * np.exp(-((progress - 0.72) / 0.16) ** 2)
        peak = 53.0
    else:
        peak = (31.0, 48.0, 39.0, 57.0)[event_index % 4]
        pulse_shape = (1.1, 1.7, 1.35, 1.0)[event_index % 4]
        pulse = np.sin(np.pi * progress) ** pulse_shape
        if event_index % 2 == 1:
            pulse = 0.78 * pulse + 0.23 * np.exp(-((progress - 0.68) / 0.17) ** 2)

    spatial_scale = np.linspace(0.84, 1.16, station_count, dtype=np.float64)
    rng.shuffle(spatial_scale)
    common_noise = rng.normal(0.0, 1.2, size=(steps, 1))
    gauge_noise = rng.normal(0.0, 1.5, size=(steps, station_count))
    rainfall = peak * pulse[:, None] * spatial_scale[None, :] + common_noise + gauge_noise
    # Weak background drizzle makes rainfall observations informative outside the peak.
    rainfall += np.where(pulse[:, None] > 0.08, 0.0, rng.uniform(0.0, 1.2, size=(steps, station_count)))
    return np.clip(rainfall, 0.0, 500.0)


def _atmospheric_observations(
    rng: np.random.Generator,
    rain: NDArray[np.float64],
    event_index: int,
) -> tuple[NDArray[np.float64], ...]:
    regime = event_index % 3
    temp_base = (27.0, 22.5, 25.0)[regime]
    humidity_base = (67.0, 75.0, 71.0)[regime]
    pressure_sensitivity = (0.17, 0.09, 0.22)[regime]
    wind_sensitivity = (0.38, 0.58, 0.30)[regime]
    # Some storm types are cooler and windier; temperature and pressure links vary by event.
    temperature = temp_base - (0.012, 0.028, 0.018)[regime] * rain + rng.normal(0.0, 0.45, rain.shape)
    humidity = np.clip(humidity_base + (0.30, 0.18, 0.37)[regime] * rain + rng.normal(0.0, 2.0, rain.shape), 30, 100)
    wind = np.clip(13.0 + wind_sensitivity * rain + rng.normal(0.0, 2.2, rain.shape), 0.0, 250.0)
    pressure = np.clip(1014.0 - pressure_sensitivity * rain + rng.normal(0.0, 1.4, rain.shape), 850.0, 1085.0)
    return temperature, humidity, wind, pressure


def _simulate_event(
    *,
    rng: np.random.Generator,
    event_index: int,
    steps: int,
    stations: tuple[WeatherStation, ...],
    grid: SimulationGrid,
    state: SimulationState,
    start_time: datetime,
    scenario: bool,
) -> list[WeatherObservation]:
    rainfall_by_station = _event_rainfall(rng, event_index, steps, len(stations), scenario)
    temperature, humidity, wind, pressure = _atmospheric_observations(rng, rainfall_by_station, event_index)
    weights = _interpolation_weights(grid, stations)
    records: list[WeatherObservation] = []

    for step in range(steps):
        rainfall_grid = np.tensordot(rainfall_by_station[step], weights, axes=(0, 0))
        state.rainfall_intensity_mm_hr[:] = rainfall_grid
        rain_flux = apply_rainfall(grid, state.rainfall_intensity_mm_hr, state.dt_hours)
        drainage_flux = apply_drainage(grid, state.resources, state.dt_hours)
        flow = advance_water_flow(grid, state.resources.barrier_crests_mm(grid))
        grid.water_depth_mm[:] = flow.water_depth_mm
        # These cumulative values are retained to keep the state object valid and auditable.
        state.balance.add_rain_and_drainage(
            DrainageFlux(
                precipitation_mm_cells=rain_flux.precipitation_mm_cells,
                surface_input_mm_cells=rain_flux.surface_input_mm_cells,
                infiltration_mm_cells=rain_flux.infiltration_mm_cells,
                natural_drainage_mm_cells=drainage_flux.natural_drainage_mm_cells,
                installed_drainage_mm_cells=drainage_flux.installed_drainage_mm_cells,
                pump_removal_mm_cells=drainage_flux.pump_removal_mm_cells,
            )
        )
        state.balance.boundary_outflow_mm_cells += flow.boundary_outflow_mm_cells
        state.balance.internal_transfer_mm_cells += flow.internal_transfer_mm_cells
        state.timestep_index += 1

        timestamp = (start_time + timedelta(minutes=TIMESTEP_MINUTES * step)).isoformat(timespec="seconds").replace("+00:00", "Z")
        for station_index, station in enumerate(stations):
            records.append(
                WeatherObservation(
                    timestamp=timestamp,
                    station_id=station.station_id,
                    rainfall_mm_hr=round(float(rainfall_by_station[step, station_index]), 4),
                    temperature_c=round(float(temperature[step, station_index]), 4),
                    humidity_pct=round(float(humidity[step, station_index]), 4),
                    wind_speed_kmh=round(float(wind[step, station_index]), 4),
                    pressure_hpa=round(float(pressure[step, station_index]), 4),
                    water_depth_mm=round(float(grid.water_depth_mm[station.y, station.x]), 4),
                )
            )
    return records


@lru_cache(maxsize=16)
def _cached_weather_data(
    seed: int,
    event_count: int,
    steps_per_event: int,
    scenario_steps: int,
) -> WeatherDataset:
    map_document = json.loads(_eastbank_path().read_text(encoding="utf-8"))
    stations = _load_stations(map_document)
    rng = np.random.default_rng(seed)
    historical: list[WeatherObservation] = []

    for event_index in range(event_count):
        grid, document = load_grid()
        state = SimulationState(
            grid=grid,
            map_document=document,
            seed=seed,
            rainfall_intensity_mm_hr=np.zeros((grid.height, grid.width), dtype=np.float64),
            resources=ResourceInventory(),
        )
        event_start = _DATA_START + timedelta(days=event_index)
        historical.extend(
            _simulate_event(
                rng=rng,
                event_index=event_index,
                steps=steps_per_event,
                stations=stations,
                grid=grid,
                state=state,
                start_time=event_start,
                scenario=False,
            )
        )

    scenario_grid, scenario_document = load_grid()
    scenario_state = SimulationState(
        grid=scenario_grid,
        map_document=scenario_document,
        seed=seed,
        rainfall_intensity_mm_hr=np.zeros((scenario_grid.height, scenario_grid.width), dtype=np.float64),
        resources=ResourceInventory(),
    )
    scenario_start = _DATA_START + timedelta(days=event_count + 1)
    scenario_records = _simulate_event(
        rng=rng,
        event_index=event_count,
        steps=scenario_steps,
        stations=stations,
        grid=scenario_grid,
        state=scenario_state,
        start_time=scenario_start,
        scenario=True,
    )
    return WeatherDataset(seed, tuple(historical), tuple(scenario_records), stations)


def generate_weather_data(
    seed: int = DEFAULT_SEED,
    event_count: int = DEFAULT_EVENT_COUNT,
    steps_per_event: int = DEFAULT_STEPS_PER_EVENT,
    scenario_steps: int = DEFAULT_SCENARIO_STEPS,
) -> WeatherDataset:
    """Generate historical storms and a separate, reproducible Eastbank watch.

    Each step represents ten minutes. Event count and duration can be reduced
    for tests or expanded for experiments; all station rows are time-aligned.
    """
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be an integer between 0 and 4294967295")
    if not isinstance(event_count, int) or isinstance(event_count, bool) or not 1 <= event_count <= 20:
        raise ValueError("event_count must be an integer between 1 and 20")
    if not isinstance(steps_per_event, int) or isinstance(steps_per_event, bool) or not 2 <= steps_per_event <= 144:
        raise ValueError("steps_per_event must be an integer between 2 and 144")
    if not isinstance(scenario_steps, int) or isinstance(scenario_steps, bool) or not 1 <= scenario_steps <= 144:
        raise ValueError("scenario_steps must be an integer between 1 and 144")
    return _cached_weather_data(seed, event_count, steps_per_event, scenario_steps)


def generate_historical_weather(
    seed: int = DEFAULT_SEED,
    event_count: int = DEFAULT_EVENT_COUNT,
    steps_per_event: int = DEFAULT_STEPS_PER_EVENT,
) -> tuple[WeatherObservation, ...]:
    return generate_weather_data(seed, event_count, steps_per_event).historical


def generate_eastbank_scenario(
    seed: int = DEFAULT_SEED,
    steps: int = DEFAULT_SCENARIO_STEPS,
    event_count: int = DEFAULT_EVENT_COUNT,
    steps_per_event: int = DEFAULT_STEPS_PER_EVENT,
) -> tuple[WeatherObservation, ...]:
    return generate_weather_data(seed, event_count, steps_per_event, steps).eastbank_scenario
