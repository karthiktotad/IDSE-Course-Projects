from app.main import scenario
from app.simulation.flood_engine import advance_simulation, reset_simulation, set_rainfall


def test_compatibility_scenario_endpoint_shape_uses_live_eastbank_grid() -> None:
    reset_simulation(42)
    initial = scenario()
    assert (initial.grid_width, initial.grid_height) == (32, 24)
    assert len(initial.cells) == 32 * 24
    assert min(cell.water_depth_cm for cell in initial.cells) == 0

    set_rainfall(60)
    advance_simulation()
    flooded = scenario()
    assert max(cell.water_depth_cm for cell in flooded.cells) > 0


def test_simulation_grid_has_valid_initial_nonnegative_water() -> None:
    reset = reset_simulation(7)
    assert reset["columns"] == 32 and reset["rows"] == 24
    assert all(cell["water_depth_mm"] >= 0 for cell in reset["cells"])
    assert reset["water_volume_balance"]["balanced"]
