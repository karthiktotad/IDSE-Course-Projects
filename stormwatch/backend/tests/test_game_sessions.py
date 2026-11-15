from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.main import (
    api_analytics_correlation,
    api_analytics_evaluate,
    api_analytics_moving_average,
    api_analytics_regression,
    api_analytics_statistics,
    api_game_advance,
    api_game_mission_objective,
    api_game_place_resource,
    api_game_rainfall,
    api_game_reset,
    api_game_state,
    api_new_game,
    api_start_flood_scenario,
)
from app.models import (
    GameAdvanceRequest,
    GameRainfallRequest,
    MissionObjectiveRequest,
    NewGameRequest,
    PlaceResourceRequest,
    ResetRequest,
    SessionCorrelationRequest,
    SessionEvaluationRequest,
    SessionMovingAverageRequest,
    SessionRegressionRequest,
    SessionStatisticsRequest,
)


def test_new_game_creates_an_isolated_session_with_grid_and_history() -> None:
    first = api_new_game(NewGameRequest(seed=31))
    second = api_new_game(NewGameRequest(seed=31))
    assert first["session_id"] != second["session_id"]
    assert len(first["cells"]) == 32 * 24
    assert len(first["historical_observations"]) == 4 * 36 * 4
    assert first["resources"]["budget_remaining_credits"] == 100
    assert first["mission_state"]["completed_count"] == 0
    assert "historical_observations" not in api_game_state(first["session_id"])


def test_session_rainfall_and_advance_are_backend_authoritative() -> None:
    initial = api_new_game(NewGameRequest(seed=12))
    session_id = initial["session_id"]
    rain = api_game_rainfall(session_id, GameRainfallRequest(rainfall_intensity_mm_hr=60))
    assert rain["rainfall_mm_per_hour"] == 60
    advanced = api_game_advance(session_id, GameAdvanceRequest(steps=1))
    assert advanced["elapsed_minutes"] == 10
    assert max(max(row) for row in advanced["water_depth_grid_mm"]) > 0
    assert advanced["mission_state"]["objectives"]["advance_simulation"] is True
    assert advanced["water_volume_balance"]["balanced"] is True


def test_sessions_do_not_share_rainfall_or_water_depth() -> None:
    first = api_new_game(NewGameRequest(seed=17))
    second = api_new_game(NewGameRequest(seed=17))
    api_game_rainfall(first["session_id"], GameRainfallRequest(rainfall_intensity_mm_hr=80))
    api_game_advance(first["session_id"], GameAdvanceRequest(steps=1))
    untouched = api_game_state(second["session_id"])
    assert untouched["elapsed_minutes"] == 0
    assert untouched["rainfall_mm_per_hour"] == 0
    assert max(max(row) for row in untouched["water_depth_grid_mm"]) == 0


def test_resource_placement_spends_server_budget_and_updates_inventory() -> None:
    initial = api_new_game(NewGameRequest(seed=21))
    land = next(cell for cell in initial["cells"] if cell["can_water_flow"] and not cell["building_id"] and cell["terrain_type"] not in {"river", "canal"})
    updated = api_game_place_resource(initial["session_id"], PlaceResourceRequest(resource_type="pump", x=land["x"], y=land["y"]))
    assert updated["resources"]["budget_remaining_credits"] == 60
    assert len(updated["resources"]["pumps"]) == 1
    assert updated["mission_state"]["objectives"]["place_resource"] is True


def test_full_100_credit_response_package_can_place_all_three_asset_types() -> None:
    game = api_new_game(NewGameRequest(seed=22))
    session_id = game["session_id"]
    land = next(cell for cell in game["cells"] if cell["terrain_type"] in {"grass", "park"} and cell["can_water_flow"] and not cell["building_id"])
    road = next(cell for cell in game["cells"] if cell["is_road"] and not cell["building_id"])
    placed = api_game_place_resource(session_id, PlaceResourceRequest(resource_type="pump", x=land["x"], y=land["y"]))
    placed = api_game_place_resource(session_id, PlaceResourceRequest(resource_type="barrier", x=1, y=1, direction="N"))
    placed = api_game_place_resource(session_id, PlaceResourceRequest(resource_type="rescue-boat", x=road["x"], y=road["y"]))
    assert placed["resources"]["budget_remaining_credits"] == 0
    assert len(placed["resources"]["pumps"]) == len(placed["resources"]["barriers"]) == len(placed["resources"]["rescue_boats"]) == 1


def test_invalid_resource_placement_and_session_return_http_errors() -> None:
    initial = api_new_game(NewGameRequest(seed=24))
    with pytest.raises(HTTPException) as placement:
        building = next(cell for cell in initial["cells"] if cell["building_id"])
        api_game_place_resource(
            initial["session_id"],
            PlaceResourceRequest(resource_type="pump", x=building["x"], y=building["y"]),
        )
    assert placement.value.status_code == 422
    with pytest.raises(HTTPException) as missing:
        api_game_state("unknown-session")
    assert missing.value.status_code == 404


def test_reset_restores_water_budget_resources_and_mission() -> None:
    initial = api_new_game(NewGameRequest(seed=25))
    session_id = initial["session_id"]
    api_game_rainfall(session_id, GameRainfallRequest(rainfall_intensity_mm_hr=80))
    api_game_advance(session_id, GameAdvanceRequest(steps=2))
    land = next(cell for cell in initial["cells"] if cell["can_water_flow"] and not cell["building_id"] and cell["terrain_type"] not in {"river", "canal"})
    api_game_place_resource(session_id, PlaceResourceRequest(resource_type="pump", x=land["x"], y=land["y"]))
    reset = api_game_reset(session_id, ResetRequest(seed=25))
    assert reset["elapsed_minutes"] == 0
    assert reset["rainfall_mm_per_hour"] == 0
    assert reset["resources"]["budget_remaining_credits"] == 100
    assert reset["resources"]["pumps"] == []
    assert reset["mission_state"]["completed_count"] == 0
    assert max(max(row) for row in reset["water_depth_grid_mm"]) == 0


def test_mission_progress_and_analytics_endpoints_are_computed() -> None:
    game = api_new_game(NewGameRequest(seed=33))
    session_id = game["session_id"]
    objective = api_game_mission_objective(session_id, MissionObjectiveRequest(objective_id="inspect_hospital"))
    assert objective["mission_state"]["objectives"]["inspect_hospital"] is True

    stats = api_analytics_statistics(SessionStatisticsRequest(values=[1, 2, 3], session_id=session_id))
    assert stats["mean"] == pytest.approx(2)
    average = api_analytics_moving_average(SessionMovingAverageRequest(data=[1, 2, 3], timestamps=["a", "b", "c"], window_size=2, session_id=session_id))
    assert average == {"values": [1.5, 2.5], "timestamps": ["b", "c"]}
    model = api_analytics_regression(SessionRegressionRequest(x=[1, 2, 3, 4, 5], y=[3, 5, 7, 9, 11], session_id=session_id))
    assert model["slope"] == pytest.approx(2)
    assert model["intercept"] == pytest.approx(1)
    assert model["split_method"] == "chronological"
    correlation = api_analytics_correlation(SessionCorrelationRequest(x=[1, 2, 3], y=[2, 4, 6], session_id=session_id))
    assert correlation["coefficient"] == pytest.approx(1)
    evaluation = api_analytics_evaluate(SessionEvaluationRequest(
        actual=[1, 2], moving_average_predictions=[1, 1], regression_predictions=[1, 2], timestamps=["t1", "t2"], session_id=session_id,
    ))
    assert evaluation["moving_average"]["metrics"]["mae"] == pytest.approx(0.5)
    assert evaluation["linear_regression"]["metrics"]["rmse"] == pytest.approx(0)
    state = api_game_state(session_id)
    assert "regression" in state["prediction_model_results"]
    assert "evaluation" in state["prediction_model_results"]


def test_manual_regression_line_is_calculated_by_python() -> None:
    result = api_analytics_regression(SessionRegressionRequest(
        x=[1, 2, 3, 4, 5], y=[3, 5, 7, 9, 11],
        manual_line_x=[0, 10], manual_line_y=[1, 11],
    ))
    manual = result["manual_line"]
    assert manual["slope"] == pytest.approx(1)
    assert manual["intercept"] == pytest.approx(1)
    assert manual["fitted_predictions"] == pytest.approx([2, 3, 4, 5])
    assert manual["residuals"] == pytest.approx([1, 2, 3, 4])
    assert manual["mae"] == pytest.approx(2.5)


def test_scenario_start_resets_run_and_advances_synthetic_weather() -> None:
    game = api_new_game(NewGameRequest(seed=61))
    session_id = game["session_id"]
    api_game_rainfall(session_id, GameRainfallRequest(rainfall_intensity_mm_hr=80))
    api_game_advance(session_id, GameAdvanceRequest(steps=2))

    started = api_start_flood_scenario(session_id)
    assert started["elapsed_minutes"] == 0
    assert started["scenario_progress"]["started"] is True
    assert started["scenario_progress"]["active"] is True
    assert started["scenario_progress"]["total_steps"] == 144
    assert started["rainfall_mm_per_hour"] == pytest.approx(started["scenario_progress"]["next_rainfall_mm_hr"])

    advanced = api_game_advance(session_id, GameAdvanceRequest(steps=1))
    assert advanced["elapsed_minutes"] == 10
    assert advanced["scenario_progress"]["step"] == 1
    assert advanced["water_volume_balance"]["balanced"] is True


def test_scenario_finishes_at_the_end_of_its_weather_record() -> None:
    game = api_new_game(NewGameRequest(seed=62))
    session_id = game["session_id"]
    api_start_flood_scenario(session_id)
    state = game
    for _ in range(24):
        state = api_game_advance(session_id, GameAdvanceRequest(steps=6))
    assert state["scenario_progress"]["complete"] is True
    assert state["scenario_progress"]["active"] is False
    assert state["scenario_progress"]["step"] == state["scenario_progress"]["total_steps"] == 144
    assert state["elapsed_minutes"] == 1440
    assert state["water_volume_balance"]["balanced"] is True
    assert state["response_outcome"]["finalized"] is True
    assert state["response_outcome"]["ending"] in {"The Prepared City", "The Narrow Escape", "The Flooded City"}


def test_placed_response_assets_survive_storm_preparation_and_outcome_uses_live_metrics() -> None:
    game = api_new_game(NewGameRequest(seed=63))
    session_id = game["session_id"]
    land = next(cell for cell in game["cells"] if cell["can_water_flow"] and not cell["building_id"] and cell["terrain_type"] in {"grass", "park"})
    api_game_place_resource(session_id, PlaceResourceRequest(resource_type="pump", x=land["x"], y=land["y"]))
    prepared = api_start_flood_scenario(session_id)
    assert len(prepared["resources"]["pumps"]) == 1
    assert prepared["resources"]["budget_remaining_credits"] == 60
    assert prepared["scenario_progress"]["active"] is True
    api_game_advance(session_id, GameAdvanceRequest(steps=4))
    result = api_game_state(session_id)
    assert result["response_outcome"]["score"] >= 0
    assert result["response_outcome"]["remaining_budget_credits"] == 60


def test_risk_identification_records_stable_grid_coordinates() -> None:
    from app.main import api_game_identify_risk
    from app.models import RiskIdentificationRequest

    game = api_new_game(NewGameRequest(seed=64))
    marked = api_game_identify_risk(game["session_id"], RiskIdentificationRequest(x=3, y=4))
    assert marked["mission_state"]["objectives"]["review_risk"] is True
    assert marked["response_outcome"]["risk_cells_identified"] == 1
