"""Descriptive statistics for finite, one-dimensional observation series."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class DescriptiveStatistics:
    mean: float
    median: float
    minimum: float
    maximum: float
    standard_deviation: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def _numeric_series(data: ArrayLike | Sequence[float]) -> NDArray[np.float64]:
    try:
        values = np.asarray(data, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("data must contain numeric values") from exc
    if values.ndim != 1 or values.size == 0:
        raise ValueError("data must be a non-empty one-dimensional series")
    if not np.all(np.isfinite(values)):
        raise ValueError("data must contain only finite values")
    return values


def descriptive_statistics(data: ArrayLike | Sequence[float]) -> DescriptiveStatistics:
    """Return mean, median, extrema and population standard deviation (ddof=0)."""
    values = _numeric_series(data)
    return DescriptiveStatistics(
        mean=float(np.mean(values)),
        median=float(np.median(values)),
        minimum=float(np.min(values)),
        maximum=float(np.max(values)),
        standard_deviation=float(np.std(values, ddof=0)),
    )


# Short alias makes the requested operation convenient in notebooks and API code.
summarize = descriptive_statistics


def mean(data: ArrayLike | Sequence[float]) -> float:
    return descriptive_statistics(data).mean


def median(data: ArrayLike | Sequence[float]) -> float:
    return descriptive_statistics(data).median


def minimum(data: ArrayLike | Sequence[float]) -> float:
    return descriptive_statistics(data).minimum


def maximum(data: ArrayLike | Sequence[float]) -> float:
    return descriptive_statistics(data).maximum


def standard_deviation(data: ArrayLike | Sequence[float]) -> float:
    return descriptive_statistics(data).standard_deviation
