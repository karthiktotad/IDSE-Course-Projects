"""Error metrics and same-observation holdout comparison utilities."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from app.analytics.regression import linear_regression


def _paired(actual: ArrayLike, predicted: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    try:
        actual_values = np.asarray(actual, dtype=np.float64)
        predicted_values = np.asarray(predicted, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("actual and predicted values must be numeric") from exc
    if actual_values.ndim != 1 or predicted_values.ndim != 1 or actual_values.size == 0:
        raise ValueError("actual and predicted must be non-empty one-dimensional series")
    if actual_values.size != predicted_values.size:
        raise ValueError("actual and predicted must have the same length")
    if not np.all(np.isfinite(actual_values)) or not np.all(np.isfinite(predicted_values)):
        raise ValueError("actual and predicted values must be finite")
    return actual_values, predicted_values


def mean_absolute_error(actual: ArrayLike, predicted: ArrayLike) -> float:
    actual_values, predicted_values = _paired(actual, predicted)
    return float(np.mean(np.abs(actual_values - predicted_values)))


def root_mean_squared_error(actual: ArrayLike, predicted: ArrayLike) -> float:
    actual_values, predicted_values = _paired(actual, predicted)
    return float(np.sqrt(np.mean(np.square(actual_values - predicted_values))))


@dataclass(frozen=True)
class MetricPair:
    mae: float
    rmse: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def evaluate_predictions(actual: ArrayLike, predicted: ArrayLike) -> MetricPair:
    return MetricPair(mean_absolute_error(actual, predicted), root_mean_squared_error(actual, predicted))


mae = mean_absolute_error
rmse = root_mean_squared_error


def compare_holdout_models(
    training_observations: Sequence[Any],
    test_observations: Sequence[Any],
    window_size: int = 6,
) -> dict[str, Any]:
    """Compare regression and rolling moving average on identical held-out rows.

    For each held-out timestamp, the baseline averages the preceding observed
    water depths. This is a rolling one-step-ahead baseline: prior held-out
    measurements are available by the next evaluation timestamp.
    """
    if not training_observations or not test_observations:
        raise ValueError("training and test observations must both be non-empty")
    if not isinstance(window_size, int) or isinstance(window_size, bool) or window_size < 1:
        raise ValueError("window_size must be a positive integer")

    def get(record: Any, name: str) -> float:
        return float(record[name] if isinstance(record, dict) else getattr(record, name))

    train_rain = np.asarray([get(record, "rainfall_mm_hr") for record in training_observations], dtype=np.float64)
    train_water = np.asarray([get(record, "water_depth_mm") for record in training_observations], dtype=np.float64)
    test_rain = np.asarray([get(record, "rainfall_mm_hr") for record in test_observations], dtype=np.float64)
    actual = np.asarray([get(record, "water_depth_mm") for record in test_observations], dtype=np.float64)
    model = linear_regression(train_rain, train_water)
    regression_predictions = np.asarray(model.predict(test_rain), dtype=np.float64)

    history = list(train_water)
    moving_predictions: list[float] = []
    for observation in test_observations:
        if len(history) < window_size:
            # A long user-selected window can exceed the available prefix. Use
            # every preceding observation until the full window is available.
            window = history
        else:
            window = history[-window_size:]
        moving_predictions.append(float(np.mean(window)))
        history.append(get(observation, "water_depth_mm"))
    moving = np.asarray(moving_predictions, dtype=np.float64)

    timestamps = [record["timestamp"] if isinstance(record, dict) else record.timestamp for record in test_observations]
    return {
        "sample_count": len(test_observations),
        "timestamps": timestamps,
        "actual_water_depth_mm": actual.tolist(),
        "moving_average": {
            "predictions_mm": moving.tolist(),
            "metrics": evaluate_predictions(actual, moving).to_dict(),
            "description": "Rolling one-step baseline using the preceding observed water-depth window.",
        },
        "linear_regression": {
            "predictions_mm": regression_predictions.tolist(),
            "metrics": evaluate_predictions(actual, regression_predictions).to_dict(),
            "description": "Rainfall-to-water-depth least-squares model fitted on the chronological training rows.",
        },
    }
