"""Simple least-squares regression and chronological train/test splitting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _series(values: ArrayLike, label: str) -> NDArray[np.float64]:
    try:
        result = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain numeric values") from exc
    if result.ndim != 1 or result.size == 0:
        raise ValueError(f"{label} must be a non-empty one-dimensional series")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{label} must contain only finite values")
    return result


@dataclass(frozen=True)
class RegressionResult:
    slope: float
    intercept: float
    fitted_predictions: NDArray[np.float64]
    residuals: NDArray[np.float64]
    training_observations: tuple[dict[str, Any], ...]
    prediction_line_x: tuple[float, float]
    prediction_line_y: tuple[float, float]

    def predict(self, x: ArrayLike | float) -> NDArray[np.float64] | float:
        values = np.asarray(x, dtype=np.float64)
        if not np.all(np.isfinite(values)):
            raise ValueError("prediction inputs must be finite")
        predicted = self.slope * values + self.intercept
        return float(predicted) if predicted.ndim == 0 else predicted

    def to_dict(self) -> dict[str, Any]:
        return {
            "slope": self.slope,
            "intercept": self.intercept,
            "fitted_predictions": self.fitted_predictions.tolist(),
            "residuals": self.residuals.tolist(),
            "training_observations": list(self.training_observations),
            "prediction_line": {
                "x": list(self.prediction_line_x),
                "y": list(self.prediction_line_y),
            },
        }


@dataclass(frozen=True)
class ChronologicalSplit:
    train: tuple[Any, ...]
    test: tuple[Any, ...]
    split_index: int


def linear_regression(
    x: ArrayLike,
    y: ArrayLike,
    training_observations: Sequence[dict[str, Any]] | None = None,
) -> RegressionResult:
    """Fit ``y = m*x + c`` by NumPy least squares on the supplied observations."""
    x_values, y_values = _series(x, "x"), _series(y, "y")
    if x_values.size != y_values.size:
        raise ValueError("x and y must have the same number of observations")
    if np.all(x_values == x_values[0]):
        # The slope is not identifiable; choose the constant least-squares fit.
        slope, intercept = 0.0, float(np.mean(y_values))
    else:
        design = np.column_stack((x_values, np.ones(x_values.size, dtype=np.float64)))
        coefficients, _, _, _ = np.linalg.lstsq(design, y_values, rcond=None)
        slope, intercept = float(coefficients[0]), float(coefficients[1])
    fitted = slope * x_values + intercept
    residuals = y_values - fitted
    low, high = float(np.min(x_values)), float(np.max(x_values))
    observations = tuple(training_observations or ())
    return RegressionResult(
        slope=slope,
        intercept=intercept,
        fitted_predictions=fitted,
        residuals=residuals,
        training_observations=observations,
        prediction_line_x=(low, high),
        prediction_line_y=(slope * low + intercept, slope * high + intercept),
    )


def chronological_train_test_split(
    observations: Sequence[Any], test_fraction: float = 0.2
) -> ChronologicalSplit:
    """Split an already time-ordered series without shuffling observations."""
    if not isinstance(test_fraction, (float, int)) or isinstance(test_fraction, bool):
        raise ValueError("test_fraction must be a number between 0 and 1")
    if not np.isfinite(test_fraction) or not 0.0 < float(test_fraction) < 1.0:
        raise ValueError("test_fraction must be greater than 0 and less than 1")
    if len(observations) < 2:
        raise ValueError("at least two observations are required for a chronological split")
    test_count = max(1, int(np.ceil(len(observations) * float(test_fraction))))
    split_index = len(observations) - test_count
    if split_index < 1:
        raise ValueError("the split must leave at least one training observation")
    return ChronologicalSplit(tuple(observations[:split_index]), tuple(observations[split_index:]), split_index)
