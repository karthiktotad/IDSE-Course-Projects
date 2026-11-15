"""Pearson relationships for weather observations; association is not causation."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


CORRELATION_EXPLANATION = (
    "Pearson correlation describes linear association in these observations; correlation does not establish causation."
)


def pearson_correlation(x: ArrayLike, y: ArrayLike) -> float | None:
    """Return Pearson's r, or None when it is undefined for a constant series."""
    try:
        x_values, y_values = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("x and y must contain numeric values") from exc
    if x_values.ndim != 1 or y_values.ndim != 1 or x_values.size == 0 or x_values.size != y_values.size:
        raise ValueError("x and y must be non-empty one-dimensional series of equal length")
    if not np.all(np.isfinite(x_values)) or not np.all(np.isfinite(y_values)):
        raise ValueError("x and y must contain only finite values")
    if x_values.size < 2 or np.std(x_values) == 0 or np.std(y_values) == 0:
        return None
    return float(np.corrcoef(x_values, y_values)[0, 1])


def weather_correlations(observations: Sequence[Any]) -> dict[str, Any]:
    """Summarize the four weather/water relationships used in the analysis lab."""
    if not observations:
        raise ValueError("at least one weather observation is required")

    def value(record: Any, name: str) -> float:
        return float(record[name] if isinstance(record, dict) else getattr(record, name))

    series = {
        "rainfall_water_depth": ("Rainfall and water depth", "rainfall_mm_hr", "water_depth_mm"),
        "temperature_humidity": ("Temperature and humidity", "temperature_c", "humidity_pct"),
        "pressure_wind_speed": ("Pressure and wind speed", "pressure_hpa", "wind_speed_kmh"),
        "rainfall_humidity": ("Rainfall and humidity", "rainfall_mm_hr", "humidity_pct"),
    }
    return {
        key: {
            "label": label,
            "coefficient": pearson_correlation(
                [value(record, x_key) for record in observations],
                [value(record, y_key) for record in observations],
            ),
            "sample_count": len(observations),
            "explanation": CORRELATION_EXPLANATION,
        }
        for key, (label, x_key, y_key) in series.items()
    }
