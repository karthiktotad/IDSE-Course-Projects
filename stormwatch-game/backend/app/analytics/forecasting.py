"""Station-specific training, holdout evaluation and rainfall forecasts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

import numpy as np

from app.analytics.correlation import weather_correlations
from app.analytics.evaluation import compare_holdout_models
from app.analytics.moving_average import moving_average
from app.analytics.regression import chronological_train_test_split, linear_regression
from app.analytics.statistics import descriptive_statistics
from app.analytics.weather_generator import (
    DEFAULT_EVENT_COUNT,
    DEFAULT_SEED,
    DEFAULT_STEPS_PER_EVENT,
    TIMESTEP_MINUTES,
    WeatherObservation,
    generate_weather_data,
)

DEFAULT_WINDOW_SIZE = 6
DEFAULT_TEST_FRACTION = 0.2


def _records_for_station(
    station_id: str,
    seed: int,
    event_count: int,
    steps_per_event: int,
) -> tuple[tuple[WeatherObservation, ...], str]:
    dataset = generate_weather_data(seed, event_count, steps_per_event)
    station = next((station for station in dataset.stations if station.station_id == station_id), None)
    if station is None:
        available = ", ".join(item.station_id for item in dataset.stations)
        raise ValueError(f"Unknown monitoring station '{station_id}'. Available stations: {available}")
    observations = tuple(record for record in dataset.historical if record.station_id == station_id)
    observations = tuple(sorted(observations, key=lambda record: record.timestamp))
    return observations, station.name


def _training_model(
    observations: Sequence[WeatherObservation],
    test_fraction: float,
) -> tuple[Any, Any, Any]:
    split = chronological_train_test_split(observations, test_fraction)
    training = split.train
    regression = linear_regression(
        [record.rainfall_mm_hr for record in training],
        [record.water_depth_mm for record in training],
        training_observations=[record.to_dict() for record in training],
    )
    return split, regression, training


def build_prediction_lab(
    station_id: str = "weather-central",
    seed: int = DEFAULT_SEED,
    window_size: int = DEFAULT_WINDOW_SIZE,
    event_count: int = DEFAULT_EVENT_COUNT,
    steps_per_event: int = DEFAULT_STEPS_PER_EVENT,
    test_fraction: float = DEFAULT_TEST_FRACTION,
) -> dict[str, Any]:
    """Return actual train/test observations, fit line, metrics and relationships."""
    observations, station_name = _records_for_station(station_id, seed, event_count, steps_per_event)
    if window_size > len(observations):
        raise ValueError(f"window_size cannot exceed the {len(observations)} station observations")
    split, model, training = _training_model(observations, test_fraction)
    heldout = split.test
    evaluation = compare_holdout_models(training, heldout, window_size)
    average = moving_average(observations, window_size)
    scenario = generate_weather_data(seed, event_count, steps_per_event).eastbank_scenario
    station_scenario = [record.to_dict() for record in scenario if record.station_id == station_id]

    return {
        "station": {"station_id": station_id, "name": station_name},
        "seed": seed,
        "timestep_minutes": TIMESTEP_MINUTES,
        "window_size": window_size,
        "split": {
            "method": "chronological",
            "test_fraction": test_fraction,
            "training_count": len(training),
            "heldout_count": len(heldout),
            "training_cutoff": training[-1].timestamp,
        },
        "descriptive_statistics": {
            "rainfall_mm_hr": descriptive_statistics([record.rainfall_mm_hr for record in observations]).to_dict(),
            "water_depth_mm": descriptive_statistics([record.water_depth_mm for record in observations]).to_dict(),
        },
        "correlations": weather_correlations(observations),
        "regression": {
            **model.to_dict(),
            "model_name": "Rainfall linear regression",
            "input_feature": "rainfall_mm_hr",
            "target": "water_depth_mm",
            "training_count": len(training),
            "training_cutoff": training[-1].timestamp,
        },
        "moving_average": {
            "values_mm": average.values.tolist(),
            "timestamps": list(average.timestamps),
            "description": "Trailing mean of observed water depth; each value aligns with the window end timestamp.",
        },
        "evaluation": evaluation,
        "training_observations": [record.to_dict() for record in training],
        "heldout_observations": [record.to_dict() for record in heldout],
        "eastbank_scenario": station_scenario,
        "educational_note": (
            "The displayed line is least-squares fit on the chronological training observations only. "
            "Both model scores use the same held-out timestamps. Correlation does not establish causation."
        ),
    }


def forecast_station(
    station_id: str,
    rainfall_observations: Sequence[float],
    *,
    seed: int = DEFAULT_SEED,
    interval_minutes: int = TIMESTEP_MINUTES,
    window_size: int = DEFAULT_WINDOW_SIZE,
    event_count: int = DEFAULT_EVENT_COUNT,
    steps_per_event: int = DEFAULT_STEPS_PER_EVENT,
) -> dict[str, Any]:
    """Forecast water depth from a station's rainfall inputs and trained model.

    Regression predictions use exactly the coefficients returned in
    ``model_information``; they are not clipped, so the player can see where a
    linear model extrapolates beyond physically meaningful water depths.
    """
    try:
        input_count = len(rainfall_observations)
    except TypeError as exc:
        raise ValueError("rainfall_observations must be a finite one-dimensional series") from exc
    if input_count == 0:
        raise ValueError("at least one future rainfall observation is required")
    if input_count > 144:
        raise ValueError("at most 144 future rainfall observations can be forecast at once")
    if not isinstance(interval_minutes, int) or isinstance(interval_minutes, bool) or interval_minutes < 1:
        raise ValueError("interval_minutes must be a positive integer")
    try:
        rainfall = np.asarray(rainfall_observations, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("rainfall_observations must be numeric") from exc
    if rainfall.ndim != 1 or rainfall.size == 0 or not np.all(np.isfinite(rainfall)):
        raise ValueError("rainfall_observations must be a finite one-dimensional series")
    if np.any((rainfall < 0.0) | (rainfall > 500.0)):
        raise ValueError("rainfall observations must be within 0..500 mm/hour")

    observations, station_name = _records_for_station(station_id, seed, event_count, steps_per_event)
    if window_size > len(observations):
        raise ValueError(f"window_size cannot exceed the {len(observations)} station observations")
    split, model, training = _training_model(observations, DEFAULT_TEST_FRACTION)
    evaluation = compare_holdout_models(training, split.test, window_size)
    last_time = datetime.fromisoformat(observations[-1].timestamp.replace("Z", "+00:00"))
    times = [
        (last_time + timedelta(minutes=interval_minutes * (index + 1))).astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
        for index in range(rainfall.size)
    ]
    regression_values = np.asarray(model.predict(rainfall), dtype=np.float64)
    baseline_value = float(np.mean([record.water_depth_mm for record in observations[-window_size:]]))
    forecasts = [
        {
            "prediction_time": timestamp,
            "rainfall_mm_hr": float(rain),
            "predicted_value_mm": float(predicted),
            "moving_average_baseline_mm": baseline_value,
        }
        for timestamp, rain, predicted in zip(times, rainfall, regression_values, strict=True)
    ]
    return {
        "station": {"station_id": station_id, "name": station_name},
        "predictions": forecasts,
        "model_information": {
            "name": "Rainfall linear regression",
            "equation": "predicted water depth = slope × rainfall intensity + intercept",
            "slope": model.slope,
            "intercept": model.intercept,
            "training_count": len(training),
            "training_cutoff": training[-1].timestamp,
            "seed": seed,
            "evaluation": evaluation,
        },
        "baseline_information": {
            "name": "Moving-average baseline",
            "window_size": window_size,
            "description": "The last observed water-depth window is averaged and held constant over the forecast horizon.",
        },
        "note": "Linear regression can produce negative or otherwise implausible values when extrapolated; inspect its training range.",
    }
