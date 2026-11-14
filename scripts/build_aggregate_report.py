#!/usr/bin/env python3
"""Rebuild the empirical annual-aggregate analysis used in the final report.

This script reads only the official annual Chennai crash table. It does not
read the generated event-level modeling dataset or any saved ML artifacts.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "accidents" / "chennai_road_crashes_1998_2025.csv"
FIGURES = ROOT / "reports" / "figures"
METRICS = ROOT / "results" / "metrics"
TRAIN_END_YEAR = 2020
HOLDOUT_START_YEAR = 2021
ROLLING_VALIDATION_START_YEAR = 2010

COUNT_COLUMNS = {
    "fatal_accidents": "Fatal Accidents",
    "grievous_accidents": "Grievous Injury - Accidents",
    "minor_accidents": "Minor Injury - Accidents",
    "non_injury_accidents": "Non Injury",
    "total_accidents": "Total Accidents",
}


def load_annual_data() -> pd.DataFrame:
    """Load and perform transparent structural checks on the source table."""
    df = pd.read_csv(SOURCE, encoding="utf-8-sig")
    person_columns = [
        "Fatal Killed",
        "Grievous Injurty - Injured",
        "Minor Injury - Injured",
        "Total number of persons involved",
    ]
    required = ["YEAR", *COUNT_COLUMNS.values(), *person_columns]
    missing_columns = sorted(set(required) - set(df.columns))
    if missing_columns:
        raise ValueError(f"Source file is missing required columns: {missing_columns}")

    df = df.rename(columns={"YEAR": "year", **{v: k for k, v in COUNT_COLUMNS.items()}})
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    for column in COUNT_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="raise").astype(int)
    for column in person_columns:
        df[column] = pd.to_numeric(df[column], errors="raise").astype(int)

    if df.isna().any().any():
        raise ValueError("The source has missing values in required analysis fields.")
    if df["year"].duplicated().any():
        raise ValueError("The source has duplicate years.")
    df = df.sort_values("year").reset_index(drop=True)
    expected_years = np.arange(df["year"].min(), df["year"].max() + 1)
    if not np.array_equal(df["year"].to_numpy(), expected_years):
        raise ValueError("The annual series contains a missing reporting year.")

    df["severe_accidents"] = df["fatal_accidents"] + df["grievous_accidents"]
    df["severe_share"] = df["severe_accidents"] / df["total_accidents"]
    df["reported_category_sum"] = df[list(COUNT_COLUMNS)[:-1]].sum(axis=1)
    df["category_total_difference"] = df["reported_category_sum"] - df["total_accidents"]
    df["reported_person_category_sum"] = df[
        ["Fatal Killed", "Grievous Injurty - Injured", "Minor Injury - Injured"]
    ].sum(axis=1)
    df["person_total_difference"] = df["reported_person_category_sum"] - df["Total number of persons involved"]
    df["yoy_total_change_pct"] = df["total_accidents"].pct_change() * 100
    return df


def make_models(years: np.ndarray, counts: np.ndarray) -> dict[str, object]:
    """Fit trend models using the supplied training period only."""
    year_origin = int(years[0])
    x = (years - year_origin).reshape(-1, 1)
    return {
        "Linear trend": LinearRegression().fit(x, counts),
        "Poisson trend": PoissonRegressor(alpha=0.0, max_iter=1000, tol=1e-9).fit(x, counts),
    }


def predict_next(models: dict[str, object], train_years: np.ndarray, train_counts: np.ndarray, year: int) -> dict[str, float]:
    year_origin = int(train_years[0])
    x_next = np.array([[year - year_origin]])
    predictions = {
        "Last-year baseline": float(train_counts[-1]),
        "Linear trend": float(models["Linear trend"].predict(x_next)[0]),
        "Poisson trend": float(models["Poisson trend"].predict(x_next)[0]),
    }
    return predictions


def evaluate_predictions(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(mean_squared_error(actual, predicted) ** 0.5),
        "MAPE_percent": float(np.mean(np.abs((actual - predicted) / actual)) * 100),
    }


def rolling_origin_predictions(df: pd.DataFrame) -> pd.DataFrame:
    """Predict 2010-2020 one year ahead using only earlier years each time."""
    years = df["year"].to_numpy()
    counts = df["total_accidents"].to_numpy(dtype=float)
    rows: list[dict[str, float | int]] = []

    for year in range(ROLLING_VALIDATION_START_YEAR, TRAIN_END_YEAR + 1):
        train_mask = years < year
        train_years, train_counts = years[train_mask], counts[train_mask]
        models = make_models(train_years, train_counts)
        predictions = predict_next(models, train_years, train_counts, year)
        actual = float(counts[years == year][0])
        rows.append({"year": year, "actual": actual, **predictions})

    return pd.DataFrame(rows)


def final_holdout_predictions(df: pd.DataFrame) -> pd.DataFrame:
    years = df["year"].to_numpy()
    counts = df["total_accidents"].to_numpy(dtype=float)
    train_mask = years <= TRAIN_END_YEAR
    holdout_mask = years >= HOLDOUT_START_YEAR
    train_years, train_counts = years[train_mask], counts[train_mask]
    holdout_years = years[holdout_mask]
    models = make_models(train_years, train_counts)

    rows = []
    for year, actual in zip(holdout_years, counts[holdout_mask]):
        predictions = predict_next(models, train_years, train_counts, int(year))
        rows.append({"year": int(year), "actual": float(actual), **predictions})
    return pd.DataFrame(rows)


def metric_table(cv: pd.DataFrame, holdout: pd.DataFrame) -> pd.DataFrame:
    model_names = ["Last-year baseline", "Linear trend", "Poisson trend"]
    rows = []
    for model in model_names:
        cv_scores = evaluate_predictions(cv["actual"].to_numpy(), cv[model].to_numpy())
        test_scores = evaluate_predictions(holdout["actual"].to_numpy(), holdout[model].to_numpy())
        rows.append({"model": model, **{f"rolling_cv_{k}": v for k, v in cv_scores.items()},
                     **{f"holdout_{k}": v for k, v in test_scores.items()}})
    return pd.DataFrame(rows)


def create_figures(df: pd.DataFrame, holdout: pd.DataFrame) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.titleweight": "bold"})

    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.plot(df["year"], df["total_accidents"], color="#165D8C", linewidth=2.2, marker="o", markersize=3.5)
    ax.axvspan(HOLDOUT_START_YEAR - 0.5, df["year"].max() + 0.5, color="#E69F00", alpha=0.12,
               label="Final chronological holdout (2021-2025)")
    peak = df.loc[df["total_accidents"].idxmax()]
    low = df.loc[df["total_accidents"].idxmin()]
    ax.annotate(f"Peak: {int(peak['total_accidents']):,} ({int(peak['year'])})",
                (peak["year"], peak["total_accidents"]), xytext=(-92, -38), textcoords="offset points",
                arrowprops={"arrowstyle": "->", "color": "#555"})
    ax.annotate(f"Low: {int(low['total_accidents']):,} ({int(low['year'])})",
                (low["year"], low["total_accidents"]), xytext=(8, 18), textcoords="offset points",
                arrowprops={"arrowstyle": "->", "color": "#555"})
    ax.set(title="Reported Annual Road Accidents in Chennai, 1998-2025",
           xlabel="Reporting year", ylabel="Reported accidents")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGURES / "aggregate_01_annual_accidents.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.plot(df["year"], df["severe_share"] * 100, color="#B23A48", linewidth=2.2, marker="o", markersize=3.5)
    ax.axvspan(HOLDOUT_START_YEAR - 0.5, df["year"].max() + 0.5, color="#E69F00", alpha=0.12)
    ax.set(title="Fatal and Grievous Accidents as a Share of Reported Total",
           xlabel="Reporting year", ylabel="Fatal + grievous accident count / total (%)")
    ax.set_ylim(0, max(80, float(df["severe_share"].max() * 100 + 5)))
    ax.grid(axis="y", alpha=0.25)
    ax.text(0.01, 0.02, "Annual aggregate ratio; not an incident-level severity probability.",
            transform=ax.transAxes, fontsize=9, color="#444")
    fig.tight_layout()
    fig.savefig(FIGURES / "aggregate_02_severe_share.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5.6))
    ax.plot(holdout["year"], holdout["actual"], color="#111827", marker="o", linewidth=2.6, label="Observed aggregate")
    for model, color, marker in [
        ("Last-year baseline", "#009E73", "s"),
        ("Linear trend", "#D55E00", "^"),
        ("Poisson trend", "#7B61A8", "D"),
    ]:
        ax.plot(holdout["year"], holdout[model], color=color, marker=marker, linewidth=1.8, label=model)
    ax.set(title="One-step Models Evaluated on the 2021-2025 Holdout",
           xlabel="Reporting year", ylabel="Annual accident count")
    ax.set_xticks(holdout["year"])
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(FIGURES / "aggregate_03_holdout_forecasts.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    df = load_annual_data()
    cv = rolling_origin_predictions(df)
    holdout = final_holdout_predictions(df)
    scores = metric_table(cv, holdout)

    METRICS.mkdir(parents=True, exist_ok=True)
    summary = df[["year", *COUNT_COLUMNS.keys(), "severe_accidents", "severe_share",
                  "reported_category_sum", "category_total_difference", "reported_person_category_sum",
                  "person_total_difference", "yoy_total_change_pct"]]
    summary.to_csv(METRICS / "annual_aggregate_analysis.csv", index=False, float_format="%.4f")
    cv.to_csv(METRICS / "annual_forecast_rolling_validation.csv", index=False, float_format="%.2f")
    holdout.to_csv(METRICS / "annual_forecast_holdout_predictions.csv", index=False, float_format="%.2f")
    scores.to_csv(METRICS / "annual_forecast_model_comparison.csv", index=False, float_format="%.2f")
    create_figures(df, holdout)

    print(f"Source rows: {len(df)} ({df['year'].min()}-{df['year'].max()})")
    print(f"Accident category-total mismatches: {int((df['category_total_difference'] != 0).sum())}")
    print(f"Persons-count mismatches: {int((df['person_total_difference'] != 0).sum())}")
    print("Rolling-origin validation (2010-2020) and final holdout (2021-2025):")
    print(scores.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print(f"Figures: {FIGURES}")
    print(f"Metrics: {METRICS}")


if __name__ == "__main__":
    main()
