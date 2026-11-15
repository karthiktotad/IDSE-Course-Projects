"""Trailing moving averages with explicit time alignment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class MovingAverageResult:
    values: NDArray[np.float64]
    timestamps: tuple[Any, ...]

    def to_dict(self) -> dict[str, list[Any]]:
        return {"values": self.values.tolist(), "timestamps": list(self.timestamps)}


def _extract_values_and_times(data: Any, timestamps: Sequence[Any] | None) -> tuple[NDArray[np.float64], tuple[Any, ...]]:
    if isinstance(data, np.ndarray) or (isinstance(data, Sequence) and not isinstance(data, (str, bytes))):
        items = list(data)
    else:
        try:
            items = list(data)
        except TypeError as exc:
            raise ValueError("data must be a sequence of numbers or observations") from exc
    if not items:
        raise ValueError("data must be a non-empty series")

    if timestamps is not None:
        if len(timestamps) != len(items):
            raise ValueError("timestamps and data must have the same length")
        times = tuple(timestamps)
        raw_values = items
    elif all(hasattr(item, "water_depth_mm") and hasattr(item, "timestamp") for item in items):
        raw_values = [item.water_depth_mm for item in items]
        times = tuple(item.timestamp for item in items)
    elif all(isinstance(item, Mapping) and "water_depth_mm" in item and "timestamp" in item for item in items):
        raw_values = [item["water_depth_mm"] for item in items]
        times = tuple(item["timestamp"] for item in items)
    else:
        raw_values = items
        # Numeric series have index timestamps when no external time labels exist.
        times = tuple(range(len(items)))

    try:
        values = np.asarray(raw_values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("data must contain numeric values") from exc
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("data must be a finite one-dimensional series")
    return values, times


def moving_average(
    data: ArrayLike | Sequence[Any],
    window_size: int,
    timestamps: Sequence[Any] | None = None,
) -> MovingAverageResult:
    """Compute a trailing average and label each result by the window's end time."""
    if not isinstance(window_size, int) or isinstance(window_size, bool):
        raise ValueError("window_size must be an integer")
    values, times = _extract_values_and_times(data, timestamps)
    if not 1 <= window_size <= values.size:
        raise ValueError(f"window_size must be between 1 and {values.size}")
    averaged = np.convolve(values, np.full(window_size, 1.0 / window_size), mode="valid")
    return MovingAverageResult(averaged, times[window_size - 1 :])
