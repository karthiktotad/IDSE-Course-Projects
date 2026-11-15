import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

class Cell(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    elevation_m: float
    water_depth_cm: float = Field(ge=0)

class Scenario(BaseModel):
    title: str
    city: str
    seed: int
    elapsed_hours: int
    grid_width: int
    grid_height: int
    rainfall_mm_per_hour: float
    cells: list[Cell]


class RainfallRequest(BaseModel):
    rainfall_intensity_mm_hr: float = Field(ge=0, le=500)


class AdvanceRequest(BaseModel):
    steps: int = Field(default=1, ge=1, le=144)


class GridPosition(BaseModel):
    x: int = Field(ge=0, le=31)
    y: int = Field(ge=0, le=23)


class BarrierRequest(GridPosition):
    direction: Literal["N", "E", "S", "W"]
    height_mm: float = Field(default=300, gt=0, le=10000)
    deployment_cost: int = Field(default=850, ge=0)


class PumpRequest(GridPosition):
    drainage_capacity_mm_hr: float = Field(default=40, gt=0, le=500)
    operating_radius_cells: float = Field(default=2.5, gt=0, le=20)
    deployment_cost: int = Field(default=4500, ge=0)


class RescueBoatRequest(GridPosition):
    deployment_cost: int = Field(default=3200, ge=0)


class ResetRequest(BaseModel):
    seed: int = Field(default=2406, ge=0, le=2**32 - 1)


class ForecastRequest(BaseModel):
    station_id: str = Field(min_length=1, max_length=64)
    rainfall_observations: list[float] = Field(min_length=1, max_length=144)
    seed: int = Field(default=2406, ge=0, le=2**32 - 1)
    interval_minutes: int = Field(default=10, ge=1, le=1440)
    window_size: int = Field(default=6, ge=1, le=144)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("rainfall_observations")
    @classmethod
    def validate_rainfall(cls, values: list[float]) -> list[float]:
        if any(not math.isfinite(value) or not 0 <= value <= 500 for value in values):
            raise ValueError("rainfall observations must be finite and within 0..500 mm/hour")
        return values


class NewGameRequest(BaseModel):
    seed: int = Field(default=2406, ge=0, le=2**32 - 1)


class GameRainfallRequest(BaseModel):
    rainfall_intensity_mm_hr: float = Field(ge=0, le=500)


class GameAdvanceRequest(BaseModel):
    steps: int = Field(default=1, ge=1, le=6)


class PlaceResourceRequest(GridPosition):
    resource_type: Literal["pump", "barrier", "rescue-boat"]
    direction: Literal["N", "E", "S", "W"] | None = None

    @model_validator(mode="after")
    def barrier_needs_direction(self) -> "PlaceResourceRequest":
        if self.resource_type == "barrier" and self.direction is None:
            raise ValueError("Barrier placements require a direction")
        return self


class MissionObjectiveRequest(BaseModel):
    objective_id: str = Field(min_length=1, max_length=64)


class RiskIdentificationRequest(BaseModel):
    x: int = Field(ge=0, lt=32)
    y: int = Field(ge=0, lt=24)


class SessionStatisticsRequest(BaseModel):
    values: list[float] = Field(min_length=1, max_length=100_000)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)


class SessionMovingAverageRequest(BaseModel):
    data: list[float] = Field(min_length=1, max_length=100_000)
    timestamps: list[str] | None = None
    window_size: int = Field(ge=1, le=100_000)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def matching_timestamps(self) -> "SessionMovingAverageRequest":
        if self.timestamps is not None and len(self.timestamps) != len(self.data):
            raise ValueError("timestamps and data must have the same length")
        return self


class SessionRegressionRequest(BaseModel):
    x: list[float] = Field(min_length=2, max_length=100_000)
    y: list[float] = Field(min_length=2, max_length=100_000)
    test_fraction: float = Field(default=0.2, gt=0, lt=1)
    manual_line_x: list[float] | None = Field(default=None, min_length=2, max_length=2)
    manual_line_y: list[float] | None = Field(default=None, min_length=2, max_length=2)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def matching_series(self) -> "SessionRegressionRequest":
        if len(self.x) != len(self.y):
            raise ValueError("x and y must have the same number of observations")
        if any(not math.isfinite(value) for value in (*self.x, *self.y)):
            raise ValueError("x and y must contain only finite values")
        if (self.manual_line_x is None) != (self.manual_line_y is None):
            raise ValueError("manual_line_x and manual_line_y must be supplied together")
        if self.manual_line_x is not None:
            values = (*self.manual_line_x, *self.manual_line_y)
            if any(not math.isfinite(value) for value in values):
                raise ValueError("manual line endpoints must be finite")
            if self.manual_line_x[0] == self.manual_line_x[1]:
                raise ValueError("manual line endpoints must have different rainfall values")
        return self


class SessionCorrelationRequest(BaseModel):
    x: list[float] = Field(min_length=1, max_length=100_000)
    y: list[float] = Field(min_length=1, max_length=100_000)
    x_label: str = Field(default="x", max_length=64)
    y_label: str = Field(default="y", max_length=64)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def matching_series(self) -> "SessionCorrelationRequest":
        if len(self.x) != len(self.y):
            raise ValueError("x and y must have the same number of observations")
        if any(not math.isfinite(value) for value in (*self.x, *self.y)):
            raise ValueError("x and y must contain only finite values")
        return self


class SessionEvaluationRequest(BaseModel):
    actual: list[float] = Field(min_length=1, max_length=100_000)
    moving_average_predictions: list[float] = Field(min_length=1, max_length=100_000)
    regression_predictions: list[float] = Field(min_length=1, max_length=100_000)
    timestamps: list[str] | None = None
    session_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def matching_series(self) -> "SessionEvaluationRequest":
        sizes = {len(self.actual), len(self.moving_average_predictions), len(self.regression_predictions)}
        if len(sizes) != 1:
            raise ValueError("actual and prediction series must have the same length")
        if self.timestamps is not None and len(self.timestamps) != len(self.actual):
            raise ValueError("timestamps must match the evaluation series length")
        if any(not math.isfinite(value) for value in (*self.actual, *self.moving_average_predictions, *self.regression_predictions)):
            raise ValueError("evaluation values must be finite")
        return self
