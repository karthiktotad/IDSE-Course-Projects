from __future__ import annotations

import numpy as np
import pytest

from app.analytics.correlation import pearson_correlation, weather_correlations
from app.analytics.evaluation import (
    compare_holdout_models,
    mean_absolute_error,
    root_mean_squared_error,
)
from app.analytics.forecasting import build_prediction_lab, forecast_station
from app.analytics.moving_average import moving_average
from app.analytics.regression import chronological_train_test_split, linear_regression
from app.analytics.statistics import descriptive_statistics
from app.analytics.weather_generator import generate_weather_data


def test_descriptive_statistics_match_hand_calculated_example() -> None:
    stats = descriptive_statistics([1, 2, 3, 4])
    assert stats.mean == pytest.approx(2.5)
    assert stats.median == pytest.approx(2.5)
    assert stats.minimum == 1
    assert stats.maximum == 4
    assert stats.standard_deviation == pytest.approx(np.sqrt(1.25))


def test_moving_average_values_align_with_window_end_timestamps() -> None:
    result = moving_average([1, 2, 3, 4], window_size=2, timestamps=["a", "b", "c", "d"])
    np.testing.assert_allclose(result.values, [1.5, 2.5, 3.5])
    assert result.timestamps == ("b", "c", "d")


def test_moving_average_reads_observation_time_and_water_depth() -> None:
    records = generate_weather_data(seed=15, event_count=1, steps_per_event=4).historical
    station_records = [record for record in records if record.station_id == "weather-central"]
    result = moving_average(station_records, 2)
    assert result.timestamps == tuple(record.timestamp for record in station_records[1:])
    assert len(result.values) == len(station_records) - 1


def test_linear_regression_coefficients_predictions_and_residuals() -> None:
    model = linear_regression([1, 2, 3], [3, 5, 7], training_observations=[{"rainfall": 1}])
    assert model.slope == pytest.approx(2)
    assert model.intercept == pytest.approx(1)
    np.testing.assert_allclose(model.fitted_predictions, [3, 5, 7])
    np.testing.assert_allclose(model.residuals, [0, 0, 0], atol=1e-12)
    assert model.predict(4) == pytest.approx(9)
    assert model.training_observations == ({"rainfall": 1},)
    assert model.prediction_line_x == (1, 3)
    assert model.prediction_line_y == pytest.approx((3, 7))


def test_zero_variance_regression_input_has_safe_constant_fit() -> None:
    model = linear_regression([5, 5, 5], [2, 4, 6])
    assert model.slope == 0
    assert model.intercept == pytest.approx(4)
    np.testing.assert_allclose(model.predict([0, 5, 10]), [4, 4, 4])


def test_pearson_correlation_positive_negative_and_undefined() -> None:
    assert pearson_correlation([1, 2, 3], [2, 4, 6]) == pytest.approx(1)
    assert pearson_correlation([1, 2, 3], [6, 4, 2]) == pytest.approx(-1)
    assert pearson_correlation([1, 1, 1], [2, 3, 4]) is None


def test_weather_correlation_explains_non_causal_association() -> None:
    rows = generate_weather_data(seed=3, event_count=1, steps_per_event=5).historical
    result = weather_correlations([row for row in rows if row.station_id == "weather-north"])
    assert set(result) == {"rainfall_water_depth", "temperature_humidity", "pressure_wind_speed", "rainfall_humidity"}
    assert all("does not establish causation" in pair["explanation"] for pair in result.values())


def test_error_metrics_match_hand_calculated_example() -> None:
    actual, predicted = [1, 2, 3], [1, 4, 2]
    assert mean_absolute_error(actual, predicted) == pytest.approx(1)
    assert root_mean_squared_error(actual, predicted) == pytest.approx(np.sqrt(5 / 3))


def test_chronological_split_does_not_shuffle() -> None:
    split = chronological_train_test_split(["t0", "t1", "t2", "t3", "t4"], test_fraction=0.4)
    assert split.train == ("t0", "t1", "t2")
    assert split.test == ("t3", "t4")
    assert split.split_index == 3


def test_holdout_models_compare_the_same_unseen_observations() -> None:
    train = [
        {"timestamp": f"t{index}", "rainfall_mm_hr": float(index), "water_depth_mm": float(index * 2)}
        for index in range(1, 4)
    ]
    test = [
        {"timestamp": f"t{index}", "rainfall_mm_hr": float(index), "water_depth_mm": float(index * 2)}
        for index in range(4, 6)
    ]
    result = compare_holdout_models(train, test, window_size=2)
    assert result["timestamps"] == ["t4", "t5"]
    assert result["sample_count"] == len(test)
    assert len(result["moving_average"]["predictions_mm"]) == len(test)
    assert len(result["linear_regression"]["predictions_mm"]) == len(test)
    assert result["linear_regression"]["metrics"]["mae"] == pytest.approx(0, abs=1e-12)


def test_weather_generator_is_seeded_and_station_complete() -> None:
    first = generate_weather_data(seed=99, event_count=2, steps_per_event=8, scenario_steps=5)
    second = generate_weather_data(seed=99, event_count=2, steps_per_event=8, scenario_steps=5)
    assert first == second
    assert {record.station_id for record in first.historical} == {station.station_id for station in first.stations}
    assert len(first.historical) == 2 * 8 * len(first.stations)
    assert len(first.eastbank_scenario) == 5 * len(first.stations)
    assert all(record.water_depth_mm >= 0 for record in first.historical)


def test_rainfall_is_physically_related_to_observed_water_depth() -> None:
    data = generate_weather_data(seed=2406)
    observations = [record for record in data.historical if record.station_id == "weather-central"]
    relationship = pearson_correlation(
        [record.rainfall_mm_hr for record in observations],
        [record.water_depth_mm for record in observations],
    )
    assert relationship is not None and relationship > 0.5


def test_prediction_lab_line_is_fit_from_its_reported_training_rows() -> None:
    lab = build_prediction_lab("weather-north", seed=17)
    train = lab["training_observations"]
    model = linear_regression(
        [record["rainfall_mm_hr"] for record in train],
        [record["water_depth_mm"] for record in train],
    )
    assert lab["regression"]["slope"] == pytest.approx(model.slope)
    assert lab["regression"]["intercept"] == pytest.approx(model.intercept)
    assert len(lab["evaluation"]["moving_average"]["predictions_mm"]) == len(lab["heldout_observations"])
    assert len(lab["evaluation"]["linear_regression"]["predictions_mm"]) == len(lab["heldout_observations"])


def test_forecast_uses_coefficients_returned_with_model() -> None:
    result = forecast_station("weather-central", [10, 20], seed=29)
    model = result["model_information"]
    expected = [model["slope"] * rain + model["intercept"] for rain in (10, 20)]
    assert [item["predicted_value_mm"] for item in result["predictions"]] == pytest.approx(expected)
    assert result["predictions"][0]["prediction_time"] < result["predictions"][1]["prediction_time"]


@pytest.mark.parametrize(
    "call",
    [
        lambda: descriptive_statistics([]),
        lambda: descriptive_statistics([1, float("nan")]),
        lambda: moving_average([1, 2], 0),
        lambda: moving_average([1, 2], 3),
        lambda: moving_average([1, 2], 1, timestamps=["only-one"]),
        lambda: linear_regression([1, 2], [1]),
        lambda: linear_regression([1, float("inf")], [2, 3]),
        lambda: pearson_correlation([1, 2], [1]),
        lambda: mean_absolute_error([1], [1, 2]),
        lambda: root_mean_squared_error([], []),
        lambda: chronological_train_test_split([1], 0.2),
        lambda: chronological_train_test_split([1, 2], 1.0),
        lambda: forecast_station("weather-central", [float("nan")]),
        lambda: forecast_station("missing-station", [10]),
    ],
)
def test_invalid_analytics_inputs_are_rejected(call) -> None:
    with pytest.raises(ValueError):
        call()
