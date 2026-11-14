"""Evidence-first execution dashboard for the Chennai road-safety study."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Chennai Road Safety | Research Dashboard",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
SOURCE_PATH = ROOT / "data/raw/accidents/chennai_road_crashes_1998_2025.csv"
METRICS_PATH = ROOT / "results/metrics"
BUILD_SCRIPT = ROOT / "scripts/build_aggregate_report.py"


@st.cache_data
def load_artifacts() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load source records and reproducible outputs from the aggregate pipeline."""
    source = pd.read_csv(SOURCE_PATH, encoding="utf-8-sig")
    annual = pd.read_csv(METRICS_PATH / "annual_aggregate_analysis.csv")
    comparison = pd.read_csv(METRICS_PATH / "annual_forecast_model_comparison.csv")
    holdout = pd.read_csv(METRICS_PATH / "annual_forecast_holdout_predictions.csv")
    rolling = pd.read_csv(METRICS_PATH / "annual_forecast_rolling_validation.csv")
    return source, annual, comparison, holdout, rolling


try:
    source_df, annual_df, model_metrics, holdout_df, rolling_df = load_artifacts()
except (FileNotFoundError, pd.errors.EmptyDataError) as exc:
    st.error(f"The analysis outputs are missing. Rebuild them from the sidebar. Details: {exc}")
    st.stop()


years = annual_df["year"].astype(int)
latest = annual_df.iloc[-1]
peak = annual_df.loc[annual_df["total_accidents"].idxmax()]
trough = annual_df.loc[annual_df["total_accidents"].idxmin()]
from_start = (latest["total_accidents"] / annual_df.iloc[0]["total_accidents"] - 1) * 100
from_trough = (latest["total_accidents"] / trough["total_accidents"] - 1) * 100
data_missing = int(source_df.isna().sum().sum())
duplicate_years = int(source_df["YEAR"].duplicated().sum())
year_range = range(int(years.min()), int(years.max()) + 1)
continuous_years = list(years) == list(year_range)
category_issues = annual_df[annual_df["category_total_difference"] != 0]
person_issues = annual_df[annual_df["person_total_difference"] != 0]


st.sidebar.title("🚦 Research workflow")
st.sidebar.caption("Follow the evidence from source data to forecast interpretation.")
page = st.sidebar.radio(
    "Project stages",
    [
        "Project question & pipeline",
        "1 · Data preparation & audit",
        "2 · Exploratory data analysis",
        "3 · Modelling & analysis",
        "4 · Evaluation & interpretation",
        "5 · Reproducibility & limitations",
    ],
)
st.sidebar.markdown("---")
if st.sidebar.button("Rebuild analysis from source", width="stretch"):
    with st.spinner("Validating the source and rebuilding all analysis outputs…"):
        result = subprocess.run(
            [sys.executable, str(BUILD_SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
    if result.returncode == 0:
        load_artifacts.clear()
        st.sidebar.success("Analysis rebuilt successfully.")
        st.rerun()
    else:
        st.sidebar.error("The analysis build failed. See the details below.")
        st.error(result.stderr or result.stdout or "The report builder returned an error.")
st.sidebar.caption("Source: Greater Chennai Police annual crash counts (1998–2025).")


if page == "Project question & pipeline":
    st.title("Chennai Road Safety: From Data to Forecast")
    st.markdown(
        "### What do the reported annual crash counts show, and how well can simple models forecast them?"
    )
    st.write(
        "This dashboard makes each analysis step visible. The empirical study uses the official "
        "annual aggregate table; it does not treat generated crash-like records as observed incidents."
    )
    st.info(
        "**Scope matters:** the available Chennai source contains annual totals, not individual crash records. "
        "So the defensible prediction task here is forecasting annual reported counts. "
        "It cannot estimate an individual crash's severity or location risk."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Annual observations", f"{len(annual_df)}")
    c2.metric("Coverage", f"{int(years.min())}–{int(years.max())}")
    c3.metric("Final holdout", "2021–2025")
    c4.metric("Forecast approaches", "3")

    st.subheader("Execution path")
    stages = st.columns(5)
    for column, title, detail in zip(
        stages,
        ["Prepare", "Explore", "Model", "Evaluate", "Interpret"],
        ["Check source, types, years, and totals", "Plot annual counts and severe share", "Baseline, linear trend, Poisson trend", "Rolling validation + untouched final years", "Explain errors, limits, and next steps"],
    ):
        column.markdown(f"**{title}**")
        column.caption(detail)

    st.subheader("What the source currently says")
    st.write(
        f"Recorded annual accidents range from **{int(trough['total_accidents']):,} in {int(trough['year'])}** "
        f"to **{int(peak['total_accidents']):,} in {int(peak['year'])}**. "
        f"The latest reported total, **{int(latest['total_accidents']):,} in {int(latest['year'])}**, "
        f"is {abs(from_start):.1f}% {'below' if from_start < 0 else 'above'} the first year."
    )
    st.caption(
        "Counts describe police-reported annual aggregates. Changes may reflect reporting and classification "
        "as well as real-world changes; they are not exposure-adjusted risk rates."
    )

elif page == "1 · Data preparation & audit":
    st.title("1 · Data Preparation & Audit")
    st.write("The reproducible analysis starts with the raw police annual table and documents its checks before modelling.")

    a, b, c, d = st.columns(4)
    a.metric("Source rows", f"{len(source_df)}")
    b.metric("Source columns", f"{len(source_df.columns)}")
    c.metric("Missing source cells", f"{data_missing}")
    d.metric("Duplicate year rows", f"{duplicate_years}")

    st.subheader("Preparation decisions")
    st.markdown(
        """
        - Loaded the Greater Chennai Police annual CSV with its original year and count fields.
        - Converted year and count columns to numeric values; ordered records chronologically.
        - Checked required columns, missing values, duplicate years, and gaps in annual coverage.
        - Derived **fatal + grievous accidents** and its share of total reported accidents.
        - Kept the source's reported total as the forecast target; did not silently overwrite it with category sums.
        """
    )
    status1, status2 = st.columns(2)
    status1.success("Continuous annual coverage" if continuous_years else "A gap exists in the annual coverage")
    status2.success("No missing cells in source" if data_missing == 0 else f"{data_missing} missing source cells found")

    st.subheader("Internal consistency checks")
    st.write(
        "Accident categories should sum to the reported total, and person categories should reconcile with "
        "the reported persons-involved total. Differences are surfaced below and retained for review."
    )
    issues = []
    for _, row in category_issues.iterrows():
        issues.append({
            "Check": "Accident category sum − reported total",
            "Year": int(row["year"]),
            "Difference": int(row["category_total_difference"]),
        })
    for _, row in person_issues.iterrows():
        issues.append({
            "Check": "Person category sum − reported persons involved",
            "Year": int(row["year"]),
            "Difference": int(row["person_total_difference"]),
        })
    if issues:
        st.warning(f"Found {len(issues)} reconciliation exception(s); source values were not edited.")
        st.dataframe(pd.DataFrame(issues), hide_index=True, width="stretch")
    else:
        st.success("All reported category sums reconcile.")

    with st.expander("Show prepared annual analysis table"):
        st.dataframe(annual_df, hide_index=True, width="stretch")

elif page == "2 · Exploratory data analysis":
    st.title("2 · Exploratory Data Analysis")
    st.write("Written observations accompany the plots so the dashboard explains the patterns, not just displays them.")

    fig_counts = px.line(
        annual_df,
        x="year",
        y="total_accidents",
        markers=True,
        title="Annual reported accident counts",
        labels={"year": "Reporting year", "total_accidents": "Reported accidents"},
    )
    fig_counts.add_vrect(x0=2020.5, x1=float(years.max()) + 0.5, fillcolor="#E69F00", opacity=0.12, line_width=0,
                         annotation_text="Final holdout", annotation_position="top left")
    fig_counts.update_layout(hovermode="x unified")
    st.plotly_chart(fig_counts, width="stretch")

    severe_fig = px.line(
        annual_df,
        x="year",
        y=annual_df["severe_share"] * 100,
        markers=True,
        title="Fatal + grievous accidents as a share of reported total",
        labels={"year": "Reporting year", "y": "Aggregate share (%)"},
    )
    severe_fig.update_traces(name="Fatal + grievous share", showlegend=False)
    severe_fig.update_layout(yaxis_title="Aggregate share (%)", xaxis_title="Reporting year")
    st.plotly_chart(severe_fig, width="stretch")

    highest_swing = annual_df.assign(abs_change=annual_df["yoy_total_change_pct"].abs()).dropna().sort_values("abs_change").iloc[-1]
    obs1, obs2, obs3 = st.columns(3)
    obs1.metric("Peak year", f"{int(peak['year'])}", f"{int(peak['total_accidents']):,} accidents")
    obs2.metric("Lowest year", f"{int(trough['year'])}", f"{int(trough['total_accidents']):,} accidents")
    obs3.metric("Latest vs low", f"+{from_trough:.1f}%", f"{int(latest['year'])} compared with {int(trough['year'])}")

    st.markdown(
        f"""
        **Interpretation.** The series is not a steady decline or growth curve: it reaches a peak in {int(peak['year'])},
        falls to its minimum in {int(trough['year'])}, and rises somewhat in the latest observations. The largest
        year-to-year percentage movement is **{highest_swing['yoy_total_change_pct']:+.1f}% in {int(highest_swing['year'])}**.
        The fatal-plus-grievous share also varies substantially, so it should be read as a ratio of annual aggregate
        counts—not as the probability that an individual crash is severe.
        """
    )
    st.caption("Shaded years are reserved for final model evaluation and are shown here only as descriptive history.")

elif page == "3 · Modelling & analysis":
    st.title("3 · Modelling & Analysis")
    st.write("We compare simple, interpretable count-forecasting approaches against a persistence baseline.")

    st.subheader("Target, split, and leakage control")
    left, right = st.columns(2)
    left.markdown(
        "**Target:** total reported accidents in a calendar year.  \n"
        "**Training period:** 1998–2020 (23 annual observations).  \n"
        "**Final holdout:** 2021–2025 (5 later observations)."
    )
    right.markdown(
        "**Rolling validation:** one-year-ahead predictions for 2010–2020 (11 folds).  \n"
        "Each fold fits using earlier years only. The final models are fitted through 2020, then evaluated on 2021–2025."
    )

    st.subheader("Compared approaches")
    st.dataframe(
        pd.DataFrame([
            {"Approach": "Last-year baseline", "How it works": "Carries the latest available count forward; a strong simple benchmark for a short time series."},
            {"Approach": "Linear trend", "How it works": "Fits a straight-line relationship between year and annual count."},
            {"Approach": "Poisson trend", "How it works": "Models a non-negative count with a log-linked year trend."},
        ]),
        hide_index=True,
        width="stretch",
    )
    st.info(
        "Only 28 annual observations are available. The source does not contain incident-level time, lighting, "
        "weather, vehicle, or location fields, so those variables are not used in this empirical model."
    )

    st.subheader("What the fitted models produce on the final holdout")
    model_order = ["Last-year baseline", "Linear trend", "Poisson trend"]
    fig = px.line(
        holdout_df,
        x="year",
        y=["actual", *model_order],
        markers=True,
        title="Observed annual counts and forecasts, 2021–2025",
        labels={"year": "Reporting year", "value": "Annual accidents", "variable": "Series"},
    )
    fig.update_xaxes(tickmode="array", tickvals=holdout_df["year"], ticktext=holdout_df["year"].astype(str))
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, width="stretch")
    st.caption("The full 2021–2025 holdout was withheld from model fitting. Forecast values are annual totals, not individual-level predictions.")
    with st.expander("Show the 11 rolling-origin validation predictions"):
        st.dataframe(rolling_df.round(2), hide_index=True, width="stretch")

elif page == "4 · Evaluation & interpretation":
    st.title("4 · Evaluation & Interpretation")
    st.write("We compare models on both rolling-origin validation and the later final holdout; lower errors are better.")

    display_metrics = model_metrics.rename(columns={
        "model": "Model",
        "rolling_cv_MAE": "Rolling MAE",
        "rolling_cv_RMSE": "Rolling RMSE",
        "rolling_cv_MAPE_percent": "Rolling MAPE (%)",
        "holdout_MAE": "Holdout MAE",
        "holdout_RMSE": "Holdout RMSE",
        "holdout_MAPE_percent": "Holdout MAPE (%)",
    })
    st.dataframe(display_metrics.round(2), hide_index=True, width="stretch")
    best_holdout = model_metrics.loc[model_metrics["holdout_MAE"].idxmin()]
    best_cv = model_metrics.loc[model_metrics["rolling_cv_MAE"].idxmin()]
    m1, m2 = st.columns(2)
    m1.metric("Lowest final holdout MAE", str(best_holdout["model"]), f"{best_holdout['holdout_MAE']:,.0f} accidents")
    m2.metric("Lowest rolling MAE", str(best_cv["model"]), f"{best_cv['rolling_cv_MAE']:,.0f} accidents")

    st.subheader("Per-year holdout errors")
    error_table = holdout_df.copy()
    error_table["Baseline error"] = error_table["Last-year baseline"] - error_table["actual"]
    error_table["Linear trend error"] = error_table["Linear trend"] - error_table["actual"]
    error_table["Poisson trend error"] = error_table["Poisson trend"] - error_table["actual"]
    st.dataframe(error_table[["year", "actual", "Last-year baseline", "Linear trend", "Poisson trend", "Baseline error", "Linear trend error", "Poisson trend error"]].round(0), hide_index=True, width="stretch")

    st.markdown(
        f"""
        **Reading the results.** The last-year baseline has the lowest MAE in both evaluations
        (rolling validation: **{best_cv['rolling_cv_MAE']:,.0f}**; final holdout: **{best_holdout['holdout_MAE']:,.0f}**).
        The two trend models overpredict the 2021–2025 counts by a wide margin. That is evidence that a single smooth
        historical trend does not generalize across the sharp changes in this series. The baseline is the most
        defensible of these three for a reference forecast, but errors remain large enough that it should not be used
        alone for operational decisions.
        """
    )

    with st.expander("What the evaluation metrics mean"):
        st.markdown(
            "- **MAE:** average absolute miss, in accidents per year.  \n"
            "- **RMSE:** like MAE, but penalizes large misses more strongly.  \n"
            "- **MAPE:** average absolute miss as a percentage of the actual count; it can be unstable when actual values are small."
        )
    st.warning(
        "These are forecasting errors against reported annual counts. They do not measure individual crash severity, "
        "causal effects, or road-level safety risk."
    )

elif page == "5 · Reproducibility & limitations":
    st.title("5 · Reproducibility, Limitations & Next Steps")
    st.write("The same source-to-results workflow can be rebuilt locally from the repository.")

    st.subheader("Reproduce the analysis")
    st.code("python scripts/build_aggregate_report.py\nstreamlit run app.py", language="bash")
    st.markdown(
        "**Source file:** `data/raw/accidents/chennai_road_crashes_1998_2025.csv`  \n"
        "**Analysis code:** `scripts/build_aggregate_report.py`  \n"
        "**Written outputs:** `results/metrics/annual_*.csv` and `reports/figures/aggregate_*.png`"
    )
    st.write(
        "The report builder checks the expected source columns, parses numeric fields, verifies year uniqueness and "
        "continuity, derives aggregate features, performs rolling and final-holdout evaluation, and writes all tables "
        "and figures. Its model splits are fixed by year, so results are reproducible."
    )

    st.subheader("Limitations that affect the conclusions")
    st.markdown(
        """
        - **Small sample:** 28 annual rows provide little information for complex forecasting models.
        - **Aggregate-only source:** no individual incidents, traffic exposure, or road-level denominators are available.
        - **Changing patterns:** large year-to-year movements may reflect changes in conditions, reporting, or definitions.
        - **Source reconciliation:** reported categories do not reconcile in every year; the 2013 accident-category difference and 2015 persons-count difference are retained and disclosed.
        - **No causal claim:** these trends and forecasts do not establish why crashes changed.
        - **Synthetic prototype outputs:** older event-level severity, SHAP, weather-linkage, and hotspot artifacts are not empirical evidence and are intentionally excluded from the findings in this dashboard. See `DATA_INTEGRITY_NOTICE.md`.
        """
    )
    st.subheader("Data needed for the next research phase")
    st.write(
        "Obtain an incident-level Chennai crash dataset with a stable crash identifier, timestamp, location, "
        "severity definition, road context, and source documentation; then join validated traffic exposure and "
        "weather records. Only after that can incident-level severity or location-risk models be evaluated credibly."
    )
    st.markdown("Source documentation: [OpenCity — Chennai Road Crashes Data](https://data.opencity.in/dataset/chennai-road-crashes-data).")
