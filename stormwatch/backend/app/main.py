import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.models import (
    AdvanceRequest,
    BarrierRequest,
    ForecastRequest,
    GameAdvanceRequest,
    GameRainfallRequest,
    MissionObjectiveRequest,
    NewGameRequest,
    PlaceResourceRequest,
    RiskIdentificationRequest,
    PumpRequest,
    RainfallRequest,
    ResetRequest,
    RescueBoatRequest,
    SessionCorrelationRequest,
    SessionEvaluationRequest,
    SessionMovingAverageRequest,
    SessionRegressionRequest,
    SessionStatisticsRequest,
    Scenario,
)
from app.simulation import flood_engine
from app.analytics import forecasting, weather_generator
from app.analytics.correlation import CORRELATION_EXPLANATION, pearson_correlation
from app.analytics.evaluation import evaluate_predictions
from app.analytics.moving_average import moving_average
from app.analytics.regression import chronological_train_test_split, linear_regression
from app.analytics.statistics import descriptive_statistics
from app.game_sessions import game_sessions

app = FastAPI(title="STORMWATCH Simulation API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "stormwatch-simulation"}


@app.post("/api/game/new")
def api_new_game(request: NewGameRequest = NewGameRequest()) -> dict:
    try:
        return game_sessions.new_game(request.seed)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not start Eastbank game: {exc}") from exc


@app.get("/api/game/{session_id}/state")
def api_game_state(session_id: str) -> dict:
    try:
        return game_sessions.get_state(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/game/{session_id}/rainfall")
def api_game_rainfall(session_id: str, request: GameRainfallRequest) -> dict:
    try:
        return game_sessions.set_rainfall(session_id, request.rainfall_intensity_mm_hr)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/game/{session_id}/advance")
def api_game_advance(session_id: str, request: GameAdvanceRequest) -> dict:
    try:
        return game_sessions.advance(session_id, request.steps)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/game/{session_id}/scenario/start")
def api_start_flood_scenario(session_id: str) -> dict:
    try:
        return game_sessions.start_flood_scenario(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/game/{session_id}/place-resource")
def api_game_place_resource(session_id: str, request: PlaceResourceRequest) -> dict:
    try:
        return game_sessions.place_resource(session_id, request.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/game/{session_id}/mission/objective")
def api_game_mission_objective(session_id: str, request: MissionObjectiveRequest) -> dict:
    try:
        return game_sessions.report_objective(session_id, request.objective_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/game/{session_id}/identify-risk")
def api_game_identify_risk(session_id: str, request: RiskIdentificationRequest) -> dict:
    try:
        return game_sessions.identify_risk(session_id, request.x, request.y)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/game/{session_id}/reset")
def api_game_reset(session_id: str, request: ResetRequest | None = None) -> dict:
    try:
        return game_sessions.reset(session_id, request.seed if request is not None else None)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _validate_optional_session(session_id: str | None) -> None:
    if session_id:
        try:
            game_sessions.validate_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/analytics/statistics")
def api_analytics_statistics(request: SessionStatisticsRequest) -> dict:
    _validate_optional_session(request.session_id)
    try:
        return {
            **descriptive_statistics(request.values).to_dict(),
            "count": len(request.values),
            "sum": float(np.sum(request.values, dtype=np.float64)),
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/analytics/moving-average")
def api_analytics_moving_average(request: SessionMovingAverageRequest) -> dict:
    _validate_optional_session(request.session_id)
    try:
        return moving_average(request.data, request.window_size, request.timestamps).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/analytics/regression")
def api_analytics_regression(request: SessionRegressionRequest) -> dict:
    _validate_optional_session(request.session_id)
    try:
        split = chronological_train_test_split(list(zip(request.x, request.y, strict=True)), request.test_fraction)
        train_x = [pair[0] for pair in split.train]
        train_y = [pair[1] for pair in split.train]
        test_x = [pair[0] for pair in split.test]
        test_y = [pair[1] for pair in split.test]
        model = linear_regression(train_x, train_y)
        result = {
            **model.to_dict(),
            "train_count": len(split.train),
            "test_count": len(split.test),
            "training_indices": list(range(split.split_index)),
            "test_indices": list(range(split.split_index, len(request.x))),
            "train_x": train_x,
            "train_y": train_y,
            "test_x": test_x,
            "test_y": test_y,
            "test_predictions": np.asarray(model.predict(test_x), dtype=np.float64).tolist(),
            "training_cutoff_index": split.split_index - 1,
            "split_method": "chronological",
        }
        if request.manual_line_x is not None and request.manual_line_y is not None:
            endpoint_x = np.asarray(request.manual_line_x, dtype=np.float64)
            endpoint_y = np.asarray(request.manual_line_y, dtype=np.float64)
            manual_slope = float((endpoint_y[1] - endpoint_y[0]) / (endpoint_x[1] - endpoint_x[0]))
            manual_intercept = float(endpoint_y[0] - manual_slope * endpoint_x[0])
            manual_predictions = manual_slope * np.asarray(train_x, dtype=np.float64) + manual_intercept
            result["manual_line"] = {
                "slope": manual_slope,
                "intercept": manual_intercept,
                "endpoint_x": request.manual_line_x,
                "endpoint_y": request.manual_line_y,
                "fitted_predictions": manual_predictions.tolist(),
                "residuals": (np.asarray(train_y, dtype=np.float64) - manual_predictions).tolist(),
                "mae": float(np.mean(np.abs(np.asarray(train_y, dtype=np.float64) - manual_predictions))),
            }
        if request.session_id:
            game_sessions.record_prediction(request.session_id, result)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/analytics/correlation")
def api_analytics_correlation(request: SessionCorrelationRequest) -> dict:
    _validate_optional_session(request.session_id)
    try:
        return {
            "x_label": request.x_label,
            "y_label": request.y_label,
            "coefficient": pearson_correlation(request.x, request.y),
            "sample_count": len(request.x),
            "explanation": CORRELATION_EXPLANATION,
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/analytics/evaluate")
def api_analytics_evaluate(request: SessionEvaluationRequest) -> dict:
    _validate_optional_session(request.session_id)
    try:
        moving = evaluate_predictions(request.actual, request.moving_average_predictions).to_dict()
        regression = evaluate_predictions(request.actual, request.regression_predictions).to_dict()
        result = {
            "sample_count": len(request.actual),
            "timestamps": request.timestamps,
            "moving_average": {"metrics": moving, "predictions": request.moving_average_predictions},
            "linear_regression": {"metrics": regression, "predictions": request.regression_predictions},
        }
        if request.session_id:
            game_sessions.record_prediction(request.session_id, result, kind="evaluation", compared=True)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/scenario", response_model=Scenario)
def scenario() -> Scenario:
    """Compatibility shape backed by the live 32×24 simulation grid."""
    state = flood_engine.get_simulation_state()
    return Scenario(
        title="The Last 24 Hours",
        city="Novara · Eastbank",
        seed=state["seed"],
        elapsed_hours=state["elapsed_minutes"] // 60,
        grid_width=state["columns"],
        grid_height=state["rows"],
        rainfall_mm_per_hour=state["rainfall_mm_per_hour"],
        cells=[
            {"x": cell["x"], "y": cell["y"],
             "elevation_m": cell["elevation_mm"] / 1000.0,
             "water_depth_cm": cell["water_depth_mm"] / 10.0}
            for cell in state["cells"]
        ],
    )


@lru_cache(maxsize=1)
def _eastbank_map() -> dict:
    map_file = Path(__file__).resolve().parents[2] / "shared" / "eastbank_grid.json"
    return json.loads(map_file.read_text(encoding="utf-8"))


@app.get("/api/map/eastbank")
def eastbank_map(seed: int = Query(default=2406, ge=0, le=2**32 - 1)) -> dict:
    """Return static map metadata plus the live Python simulation grid."""
    metadata = _eastbank_map()
    simulation = flood_engine.get_simulation_state()
    data = {key: value for key, value in metadata.items() if key != "cells"}
    data["seed"] = simulation["seed"]
    data["rainfall_mm_per_hour"] = simulation["rainfall_mm_per_hour"]
    data["cells"] = [
        {**cell, **dynamic}
        for cell, dynamic in zip(metadata["cells"], simulation["cells"])
    ]
    rng = np.random.default_rng(seed)
    readings = []
    for station in (place for place in metadata["locations"] if place["kind"] == "weather_station"):
        cell = simulation["cells"][station["y"] * metadata["columns"] + station["x"]]
        readings.append({
            "station_id": station["id"], "name": station["name"],
            "rainfall_mm_hr": cell["rainfall_intensity_mm_hr"],
            "wind_kmh": round(float(rng.normal(38, 3)), 1),
            "air_pressure_hpa": round(float(rng.normal(997, 1.5)), 1),
        })
    inventory = simulation["resources"]["inventory"]
    data["weather_observations"] = readings
    data["budget_credits"] = simulation["resources"]["budget_remaining_credits"]
    data["available_resources"] = [
        {"id": "pump", "name": "Drainage pump", "count": inventory["pumps"], "cost": 40},
        {"id": "barrier", "name": "Flood barrier", "count": inventory["barriers"], "cost": 25},
        {"id": "rescue-boat", "name": "Rescue boat", "count": inventory["rescue_boats"], "cost": 35},
    ]
    data["simulation"] = {key: simulation[key] for key in (
        "timestep_minutes", "dt_hours", "elapsed_minutes", "elapsed_seconds",
        "maximum_water_depth_mm", "average_water_depth_mm", "flooded_road_count",
        "hospital_access_status", "water_volume_balance", "resources",
    )}
    return data


@app.post("/api/simulation/initialize")
def api_initialize(request: ResetRequest = ResetRequest()) -> dict:
    return flood_engine.initialize_simulation(request.seed)


@app.get("/api/simulation/state")
def api_state() -> dict:
    return flood_engine.get_simulation_state()


@app.post("/api/simulation/rainfall")
def api_rainfall(request: RainfallRequest) -> dict:
    try:
        return flood_engine.set_rainfall(request.rainfall_intensity_mm_hr)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/simulation/advance")
def api_advance(request: AdvanceRequest) -> dict:
    try:
        return flood_engine.advance_simulation(request.steps)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/simulation/barriers")
def api_place_barrier(request: BarrierRequest) -> dict:
    try:
        return flood_engine.place_barrier((request.x, request.y), request.direction,
                                          request.height_mm, request.deployment_cost)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/simulation/pumps")
def api_place_pump(request: PumpRequest) -> dict:
    try:
        return flood_engine.place_pump((request.x, request.y), request.drainage_capacity_mm_hr,
                                       request.operating_radius_cells, request.deployment_cost)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/simulation/rescue-boats")
def api_place_rescue_boat(request: RescueBoatRequest) -> dict:
    try:
        return flood_engine.place_rescue_boat((request.x, request.y), request.deployment_cost)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/simulation/reset")
def api_reset(request: ResetRequest = ResetRequest()) -> dict:
    return flood_engine.reset_simulation(request.seed)


@app.get("/api/analytics/weather")
def api_analytics_weather(
    seed: int = Query(default=weather_generator.DEFAULT_SEED, ge=0, le=2**32 - 1),
    event_count: int = Query(default=weather_generator.DEFAULT_EVENT_COUNT, ge=1, le=20),
    steps_per_event: int = Query(default=weather_generator.DEFAULT_STEPS_PER_EVENT, ge=2, le=144),
    scenario_steps: int = Query(default=weather_generator.DEFAULT_SCENARIO_STEPS, ge=1, le=144),
) -> dict:
    try:
        return weather_generator.generate_weather_data(seed, event_count, steps_per_event, scenario_steps).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/analytics/lab")
def api_analytics_lab(
    station_id: str = Query(default="weather-central", min_length=1, max_length=64),
    seed: int = Query(default=weather_generator.DEFAULT_SEED, ge=0, le=2**32 - 1),
    window_size: int = Query(default=6, ge=1, le=144),
) -> dict:
    try:
        return forecasting.build_prediction_lab(station_id=station_id, seed=seed, window_size=window_size)
    except ValueError as exc:
        status = 404 if "Unknown monitoring station" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@app.post("/api/analytics/forecast")
def api_analytics_forecast(request: ForecastRequest) -> dict:
    try:
        _validate_optional_session(request.session_id)
        result = forecasting.forecast_station(
            station_id=request.station_id,
            rainfall_observations=request.rainfall_observations,
            seed=request.seed,
            interval_minutes=request.interval_minutes,
            window_size=request.window_size,
        )
        if request.session_id:
            game_sessions.record_prediction(request.session_id, result, kind="forecast")
        return result
    except ValueError as exc:
        status = 404 if "Unknown monitoring station" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc


# In production, serve the built Phaser application from the same origin as the
# API. Local development continues to use Vite on port 5173.
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
