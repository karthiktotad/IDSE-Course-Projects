from app.eastbank import HEIGHT, LOCATIONS, TILE_SIZE, WIDTH, build_map_document
from app.main import eastbank_map
from app.simulation.flood_engine import advance_simulation, reset_simulation, set_rainfall


def test_eastbank_grid_dimensions_and_coordinates_are_complete() -> None:
    city = build_map_document()
    assert (city["columns"], city["rows"], city["tile_size_px"]) == (32, 24, 32)
    assert (city["pixel_width"], city["pixel_height"]) == (1024, 768)
    assert len(city["cells"]) == WIDTH * HEIGHT
    assert [(cell["x"], cell["y"]) for cell in city["cells"]] == [(x, y) for y in range(HEIGHT) for x in range(WIDTH)]


def test_key_locations_and_vulnerable_hospital_approach_are_stable() -> None:
    city = build_map_document()
    locations = {place["id"]: place for place in city["locations"]}
    assert locations["eastbank-hospital"]["x"] == 13
    assert {place.kind for place in LOCATIONS} >= {"hospital", "school", "control_centre", "weather_station"}
    approach = [cell for cell in city["cells"] if cell["x"] == 12 and 12 <= cell["y"] <= 16]
    assert all(cell["terrain_type"] == "road" and cell["elevation_mm"] < 710 for cell in approach)
    assert len([place for place in city["locations"] if place["kind"] == "weather_station"]) == 4


def test_eastbank_overlay_and_weather_are_python_computed_and_seeded() -> None:
    reset_simulation(17)
    set_rainfall(22.0)
    advance_simulation()
    first = eastbank_map(17)
    repeated = eastbank_map(17)
    changed_seed = eastbank_map(18)
    assert len(first["cells"]) == 768
    assert first["cells"][0]["rainfall_intensity_mm_hr"] == repeated["cells"][0]["rainfall_intensity_mm_hr"]
    assert first["cells"][0]["rainfall_intensity_mm_hr"] == changed_seed["cells"][0]["rainfall_intensity_mm_hr"]
    assert first["cells"][0]["water_depth_mm"] > 0
    assert first["weather_observations"][0]["wind_kmh"] != changed_seed["weather_observations"][0]["wind_kmh"]
    assert all(0 <= cell["flood_risk_index"] <= 100 for cell in first["cells"])
    assert all(cell["water_depth_mm"] >= 0 for cell in first["cells"])
    assert len(first["weather_observations"]) == 4
