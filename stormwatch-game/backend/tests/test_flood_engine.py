from __future__ import annotations

import numpy as np

from app.simulation.drainage import apply_drainage
from app.simulation.flood_engine import (
    advance_simulation,
    get_simulation_state,
    initialize_simulation,
    place_pump,
    place_rescue_boat,
    reset_simulation,
    set_rainfall,
)
from app.simulation.grid import SimulationGrid, load_grid
from app.simulation.resources import ResourceInventory
from app.simulation.water_flow import advance_water_flow


def synthetic_grid(elevation: list[list[float]], terrain: list[list[str]] | None = None) -> SimulationGrid:
    elevations = np.asarray(elevation, dtype=np.float64)
    height, width = elevations.shape
    terrain_array = np.asarray(terrain or [["grass"] * width for _ in range(height)], dtype="U16")
    cell_type = np.full((height, width), "land", dtype="U16")
    cell_type[terrain_array == "river"] = "river"
    cell_type[terrain_array == "canal"] = "waterway"
    cell_type[terrain_array == "building"] = "obstacle"
    return SimulationGrid(
        width=width, height=height, cell_size_m=32.0,
        elevation_mm=elevations,
        impervious_ratio=np.zeros((height, width), dtype=np.float64),
        infiltration_rate_mm_hr=np.zeros((height, width), dtype=np.float64),
        drainage_capacity_mm_hr=np.zeros((height, width), dtype=np.float64),
        terrain_type=terrain_array, cell_type=cell_type,
        building_id=np.where(terrain_array == "building", "block", "").astype("U16"),
        district_id=np.full((height, width), "test", dtype="U16"),
        is_road=np.zeros((height, width), dtype=np.bool_),
        can_water_flow=terrain_array != "building",
        is_drain_inlet=np.zeros((height, width), dtype=np.bool_),
        water_depth_mm=np.zeros((height, width), dtype=np.float64),
    )


def test_rainfall_adds_surface_water_and_advances_ten_minutes() -> None:
    initial = initialize_simulation(2406)
    assert initial["timestep_minutes"] == 10
    set_rainfall(60.0)
    result = advance_simulation()
    assert result["elapsed_minutes"] == 10
    assert result["maximum_water_depth_mm"] > 0
    assert result["water_volume_balance"]["cumulative_rainfall_m3"] > 0


def test_downhill_flow_accumulates_more_water_in_a_low_basin() -> None:
    grid = synthetic_grid([[1000, 1000, 1000], [1000, 0, 1000], [1000, 1000, 1000]])
    grid.water_depth_mm[0, 1] = grid.water_depth_mm[1, 0] = 20
    grid.water_depth_mm[1, 2] = grid.water_depth_mm[2, 1] = 20
    result = advance_water_flow(grid, {}, max_transfer_fraction=0.5)
    assert result.water_depth_mm[1, 1] > max(result.water_depth_mm[0, 1], result.water_depth_mm[1, 0])
    assert np.sum(result.water_depth_mm) == np.sum(grid.water_depth_mm)


def test_natural_and_installed_drainage_reduce_water_depth() -> None:
    grid, _ = load_grid()
    resources = ResourceInventory()
    x, y = 14, 12  # Authored storm-drain inlet.
    assert grid.is_drain_inlet[y, x]
    grid.water_depth_mm[y, x] = 100.0
    before = float(np.sum(grid.water_depth_mm))
    flux = apply_drainage(grid, resources, 1 / 6)
    assert np.sum(grid.water_depth_mm) < before
    assert flux.installed_drainage_mm_cells > 0


def test_pump_reduces_nearby_water() -> None:
    reset_simulation(2406)
    set_rainfall(90.0)
    without_pump = advance_simulation()
    target = (12, 14)
    baseline_depth = without_pump["water_depth_grid_mm"][target[1]][target[0]]

    reset_simulation(2406)
    set_rainfall(90.0)
    place_pump(target, drainage_capacity_mm_hr=40.0, operating_radius_cells=2.5, deployment_cost=0)
    with_pump = advance_simulation()
    pumped_depth = with_pump["water_depth_grid_mm"][target[1]][target[0]]
    assert pumped_depth < baseline_depth
    assert with_pump["water_volume_balance"]["pump_removal_m3"] > 0


def test_barrier_blocks_transfer_until_source_exceeds_crest() -> None:
    grid = synthetic_grid([[0, 1000, 2000]])
    grid.water_depth_mm[0, 1] = 80
    resources = ResourceInventory()
    barrier = resources.place_barrier(grid, (1, 0), "W", height_mm=300, deployment_cost=0)
    crest = resources.barrier_crests_mm(grid)
    blocked = advance_water_flow(grid, crest, max_transfer_fraction=0.25)
    assert blocked.water_depth_mm[0, 0] == 0

    # Raising the source surface above the barrier crest permits overflow.
    grid.water_depth_mm[0, 1] = 500
    overtopped = advance_water_flow(grid, crest, max_transfer_fraction=0.25)
    assert overtopped.water_depth_mm[0, 0] > 0
    assert barrier.height_mm == 300


def test_river_water_can_overflow_to_a_lower_bank() -> None:
    grid = synthetic_grid([[800, 100, 0]], [["grass", "river", "grass"]])
    grid.water_depth_mm[0, 1] = 500
    result = advance_water_flow(grid, {}, max_transfer_fraction=0.25)
    assert result.water_depth_mm[0, 2] > 0


def test_open_west_river_boundary_outflow_is_counted() -> None:
    grid = synthetic_grid([[0]], [["river"]])
    grid.water_depth_mm[0, 0] = 100
    result = advance_water_flow(grid, {}, max_transfer_fraction=0.25)
    assert result.boundary_outflow_mm_cells == 25
    assert result.water_depth_mm[0, 0] == 75


def test_rescue_boat_can_be_placed_in_the_mapped_canal() -> None:
    reset = reset_simulation(2406)
    assert reset["resources"]["inventory"]["rescue_boats"] == 1
    placed = place_rescue_boat((10, 9), deployment_cost=0)
    assert placed["resources"]["rescue_boats"][0]["grid_position"] == {"x": 10, "y": 9}
    assert placed["resources"]["inventory"]["rescue_boats"] == 0


def test_flow_never_makes_depth_negative_or_loses_internal_water() -> None:
    grid = synthetic_grid([[0, 250, 750], [1200, 50, 500], [900, 300, 100]])
    grid.water_depth_mm[:] = np.array([[20, 0, 40], [0, 30, 10], [5, 0, 60]], dtype=np.float64)
    before = float(np.sum(grid.water_depth_mm))
    flow = advance_water_flow(grid, {}, max_transfer_fraction=0.25)
    assert float(np.min(flow.water_depth_mm)) >= 0
    assert np.isclose(np.sum(flow.water_depth_mm), before, atol=1e-10)
    assert flow.internal_transfer_mm_cells > 0
    assert flow.boundary_outflow_mm_cells == 0


def test_water_does_not_flow_into_building_obstacles() -> None:
    grid = synthetic_grid([[0, 0, 0]], [["grass", "building", "grass"]])
    grid.water_depth_mm[0, 0] = 100
    result = advance_water_flow(grid, {}, max_transfer_fraction=1.0)
    assert result.water_depth_mm[0, 1] == 0
    assert result.water_depth_mm[0, 0] == 100


def test_whole_simulation_balance_accounts_for_rain_infiltration_drainage_and_outflow() -> None:
    reset_simulation(123)
    set_rainfall(120.0)
    state = advance_simulation(steps=8)
    balance = state["water_volume_balance"]
    assert balance["cumulative_rainfall_m3"] > 0
    assert balance["infiltration_m3"] > 0
    assert balance["total_drainage_m3"] > 0
    assert balance["boundary_outflow_m3"] >= 0
    assert balance["balanced"]
    assert abs(balance["balance_error_m3"]) < 1e-7
    assert state["flooded_road_count"] >= 0
    assert state["hospital_access_status"] in {"accessible", "inaccessible", "unknown"}


def test_engine_output_is_deterministic_for_fixed_inputs_and_seed() -> None:
    initialize_simulation(77); set_rainfall(45); first = advance_simulation(3)
    initialize_simulation(77); set_rainfall(45); second = advance_simulation(3)
    assert first["water_depth_grid_mm"] == second["water_depth_grid_mm"]
    assert first["water_volume_balance"] == second["water_volume_balance"]
    assert get_simulation_state()["elapsed_seconds"] == 1800


def test_extreme_rainfall_and_many_steps_never_make_depth_negative() -> None:
    reset_simulation(4); set_rainfall(500); state = advance_simulation(20)
    assert min(min(row) for row in state["water_depth_grid_mm"]) >= 0
    assert state["water_volume_balance"]["balanced"]
