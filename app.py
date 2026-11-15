"""
Interactive Streamlit Research Dashboard.
Beyond Accident Counts: Road Accident Risk Factors, Severity and Accident-Prone Locations in Chennai.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import joblib
from pathlib import Path

# Streamlit Page Config
st.set_page_config(
    page_title="Chennai Road Accident Research Dashboard",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paths
BASE_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RESULTS_DIR = BASE_DIR / "results"
VIS_DIR = RESULTS_DIR / "visualizations"
METRICS_DIR = RESULTS_DIR / "metrics"
MAPS_DIR = RESULTS_DIR / "maps"
MODELS_DIR = BASE_DIR / "models"
AGGREGATE_SOURCE = BASE_DIR / "data" / "raw" / "accidents" / "chennai_road_crashes_1998_2025.csv"


@st.cache_data
def load_data():
    annual_df = pd.read_csv(PROCESSED_DIR / "chennai_annual_crash_severity_preprocessed.csv")
    modeling_df = pd.read_csv(PROCESSED_DIR / "chennai_accident_severity_modeling_dataset.csv")
    hotspots_df = pd.read_csv(METRICS_DIR / "geospatial_hotspots_summary.csv")
    model_comp_df = pd.read_csv(METRICS_DIR / "model_comparison_table.csv")
    odds_ratios_df = pd.read_csv(METRICS_DIR / "logistic_regression_odds_ratios.csv")
    weather_df = pd.read_csv(PROCESSED_DIR / "chennai_daily_weather_preprocessed.csv")
    return annual_df, modeling_df, hotspots_df, model_comp_df, odds_ratios_df, weather_df


annual_df, modeling_df, hotspots_df, model_comp_df, odds_ratios_df, weather_df = load_data()


@st.cache_data
def load_aggregate_workflow():
    """Load evidence artifacts from the reproducible annual-aggregate analysis."""
    source = pd.read_csv(AGGREGATE_SOURCE, encoding="utf-8-sig")
    metrics = pd.read_csv(METRICS_DIR / "annual_aggregate_analysis.csv")
    comparison = pd.read_csv(METRICS_DIR / "annual_forecast_model_comparison.csv")
    holdout = pd.read_csv(METRICS_DIR / "annual_forecast_holdout_predictions.csv")
    rolling = pd.read_csv(METRICS_DIR / "annual_forecast_rolling_validation.csv")
    return source, metrics, comparison, holdout, rolling


def render_research_workflow():
    """Show the source-to-forecast process alongside the original dashboard pages."""
    source, aggregate, comparison, holdout, rolling = load_aggregate_workflow()
    st.title("Research Workflow: From Data Preparation to Forecast Evaluation")
    st.markdown(
        "### The analysis steps behind the annual accident-count forecasting model"
    )
    st.write(
        "This added section documents how the aggregate forecasting analysis was prepared and evaluated. "
        "The original overview, severity, weather, geospatial, machine-learning, and prediction pages remain available."
    )
    st.info(
        "This research workflow uses the official annual aggregate table only. The original event-level "
        "demo pages remain illustrative because their incident-like rows are generated. See the final "
        "Policy Findings & Limitations page for the full data integrity notice."
    )

    preparation_tab, eda_tab, modeling_tab, evaluation_tab, reproducibility_tab = st.tabs(
        ["Data Preparation & Audit", "EDA", "Modelling & Analysis", "Evaluation & Interpretation", "Reproducibility & Limits"]
    )

    years = aggregate["year"].astype(int)
    peak = aggregate.loc[aggregate["total_accidents"].idxmax()]
    low = aggregate.loc[aggregate["total_accidents"].idxmin()]
    latest = aggregate.iloc[-1]

    with preparation_tab:
        st.subheader("Source and preparation")
        st.caption("Annual forecast source (1 CSV): data/raw/accidents/chennai_road_crashes_1998_2025.csv")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Annual rows", f"{len(source)}")
        c2.metric("Source columns", f"{len(source.columns)}")
        c3.metric("Missing cells", f"{int(source.isna().sum().sum())}")
        c4.metric("Duplicate years", f"{int(source['YEAR'].duplicated().sum())}")
        complete_years = list(years) == list(range(int(years.min()), int(years.max()) + 1))
        st.success(
            f"Annual coverage is continuous from {int(years.min())} to {int(years.max())}."
            if complete_years else "Annual coverage contains a missing year."
        )
        st.markdown(
            "**Preparation steps:** validate required source columns; convert year/count fields to numeric; sort by year; "
            "check missing values, duplicate years, and gaps; derive fatal-plus-grievous counts and their share of "
            "the reported total. The reported total remains the forecast target; source values are not silently corrected."
        )

        st.divider()
        st.subheader("How the separate severity-classifier data was prepared")
        st.markdown(
            "The **1 CSV above is for the annual-count analysis**. The original severity classifier follows a separate "
            "preparation path. Its trainer reads one final feature-matrix CSV, created from a generated event-level "
            "dataset that reads five upstream processed CSVs."
        )
        lineage = pd.DataFrame([
            {
                "Stage": "Upstream inputs read by the generator (5 CSVs)",
                "Files": (
                    "chennai_annual_crash_severity_preprocessed.csv; "
                    "chennai_daily_weather_preprocessed.csv; "
                    "chennai_osm_junctions_preprocessed.csv; "
                    "chennai_osm_roads_preprocessed.csv; "
                    "chennai_traffic_police_jurisdictions_preprocessed.csv"
                ),
                "Use / status": "Annual totals set severity counts; weather and jurisdiction/junction context are sampled or assigned. The roads CSV is read but not used by the current generator."
            },
            {
                "Stage": "Generated intermediate dataset",
                "Files": "chennai_accident_severity_modeling_dataset.csv",
                "Use / status": "5,035 incident-like rows calibrated to 2021 aggregate totals; not 5,035 observed crash records."
            },
            {
                "Stage": "Feature engineering output and classifier input (1 CSV)",
                "Files": "chennai_feature_matrix.csv",
                "Use / status": "The severity-model training code reads this prepared matrix, then makes an 80/20 stratified split."
            },
        ])
        st.dataframe(lineage, hide_index=True, use_container_width=True)
        st.warning(
            "The severity labels are assigned to match annual aggregate counts, and some feature values are then "
            "sampled in ways that depend on those labels. These generated records cannot validate real-world crash-severity "
            "prediction. Treat the classifier and its scores as a modeling demonstration until genuine incident-level "
            "crash records are available."
        )

        category_issues = aggregate[aggregate["category_total_difference"] != 0]
        person_issues = aggregate[aggregate["person_total_difference"] != 0]
        issues = []
        for _, row in category_issues.iterrows():
            issues.append({"Check": "Accident category sum minus reported total", "Year": int(row["year"]),
                           "Difference": int(row["category_total_difference"])})
        for _, row in person_issues.iterrows():
            issues.append({"Check": "Person category sum minus reported persons involved", "Year": int(row["year"]),
                           "Difference": int(row["person_total_difference"])})
        if issues:
            st.warning("Two source reconciliation exceptions were retained for review; neither was edited.")
            st.dataframe(pd.DataFrame(issues), hide_index=True, use_container_width=True)
        with st.expander("Inspect prepared annual table"):
            st.dataframe(aggregate, hide_index=True, use_container_width=True)

    with eda_tab:
        st.subheader("Exploratory patterns")
        accident_fig = px.line(
            aggregate, x="year", y="total_accidents", markers=True,
            title="Reported annual road accidents in Chennai",
            labels={"year": "Reporting year", "total_accidents": "Reported accidents"},
        )
        accident_fig.add_vrect(x0=2020.5, x1=float(years.max()) + 0.5, fillcolor="#E69F00",
                               opacity=0.12, line_width=0, annotation_text="Final holdout")
        st.plotly_chart(accident_fig, use_container_width=True)
        severe_fig = px.line(
            aggregate, x="year", y=aggregate["severe_share"] * 100, markers=True,
            title="Fatal + grievous accidents as a share of reported total",
            labels={"year": "Reporting year", "y": "Aggregate share (%)"},
        )
        severe_fig.update_layout(yaxis_title="Aggregate share (%)", xaxis_title="Reporting year")
        st.plotly_chart(severe_fig, use_container_width=True)
        st.markdown(
            f"**Written insight:** counts peak at **{int(peak['total_accidents']):,} in {int(peak['year'])}**, "
            f"fall to **{int(low['total_accidents']):,} in {int(low['year'])}**, and reach "
            f"**{int(latest['total_accidents']):,} in {int(latest['year'])}**. The severe-share curve is also highly variable. "
            "Because these are annual aggregates, the ratio is not the probability that an individual crash is severe."
        )

    with modeling_tab:
        st.subheader("Target and time-ordered validation")
        st.markdown(
            "**Target:** total reported accidents per year.  \n"
            "**Training:** 1998–2020 (23 observations). **Final chronological holdout:** 2021–2025 (5 observations).  \n"
            "**Rolling-origin validation:** one-year-ahead predictions for 2010–2020 (11 folds), using earlier years only in each fold."
        )
        st.dataframe(pd.DataFrame([
            {"Model": "Last-year baseline", "Method": "Carry the latest available annual count forward."},
            {"Model": "Linear trend", "Method": "Fit a straight-line relationship between year and count."},
            {"Model": "Poisson trend", "Method": "Fit a log-linked count model using year as the predictor."},
        ]), hide_index=True, use_container_width=True)
        forecast_fig = px.line(
            holdout, x="year", y=["actual", "Last-year baseline", "Linear trend", "Poisson trend"],
            markers=True, title="Observed counts and forecasts on the 2021–2025 holdout",
            labels={"year": "Reporting year", "value": "Annual accidents", "variable": "Series"},
        )
        forecast_fig.update_xaxes(
            tickmode="array",
            tickvals=holdout["year"],
            ticktext=holdout["year"].astype(str),
        )
        st.plotly_chart(forecast_fig, use_container_width=True)
        with st.expander("Show rolling-origin predictions"):
            st.dataframe(rolling.round(2), hide_index=True, use_container_width=True)
        st.caption("The data has no individual crash timestamps, lighting, vehicle, or location fields; those cannot be modeled from this source.")

    with evaluation_tab:
        st.subheader("Model comparison")
        st.write("MAE and RMSE are in accidents per year; MAPE is a percentage. Lower values indicate smaller errors.")
        st.dataframe(comparison.round(2), hide_index=True, use_container_width=True)
        best = comparison.loc[comparison["holdout_MAE"].idxmin()]
        best_cv = comparison.loc[comparison["rolling_cv_MAE"].idxmin()]
        st.markdown(
            f"**Interpretation:** the **{best['model']}** has the lowest MAE in both the final holdout "
            f"(**{best['holdout_MAE']:,.0f} accidents**) and rolling validation (**{best_cv['rolling_cv_MAE']:,.0f} accidents**). "
            "Both trend models overpredict the later holdout by a large margin. The simple baseline is the strongest "
            "reference among these candidates, but its error remains too large for stand-alone operational decisions."
        )
        errors = holdout.copy()
        for model in ["Last-year baseline", "Linear trend", "Poisson trend"]:
            errors[f"{model} error"] = errors[model] - errors["actual"]
        st.dataframe(errors.round(0), hide_index=True, use_container_width=True)
        st.warning("This evaluates annual-count forecasts, not severity probability, causal effects, or street-level risk.")

    with reproducibility_tab:
        st.subheader("Rebuild and interpret responsibly")
        st.code("python main.py --stage report\nstreamlit run app.py", language="bash")
        st.markdown(
            "The verified aggregate builder is `scripts/build_aggregate_report.py`. It reads the raw annual CSV and "
            "writes the prepared metrics, validation predictions, holdout forecasts, comparisons, and figures."
        )
        st.markdown(
            "**Limitations:** only 28 annual observations; no incident-level crash records or traffic-exposure denominator; "
            "possible changes in reporting definitions; 2013 accident-category and 2015 persons-count discrepancies; "
            "and a five-year final holdout. The older classifier, weather-linkage, and hotspot pages are generated-data "
            "demonstrations and are not used as evidence in this workflow."
        )
        st.write(
            "A credible crash-level study would need documented incident records with timestamps, locations, severity, "
            "and a stable crash identifier, plus suitable road and traffic-exposure data."
        )
        st.markdown("Source: [OpenCity — Chennai Road Crashes Data](https://data.opencity.in/dataset/chennai-road-crashes-data).")

# Sidebar Navigation
st.sidebar.title("🚦 Navigation")
nav = st.sidebar.radio(
    "Select Research Section:",
    [
        "Research Workflow: Preparation to Evaluation",
        "1. Executive Overview & Trends",
        "2. Severity & Infrastructure Risk",
        "3. Weather & Environmental Exposure",
        "4. Interactive Geospatial Hotspots",
        "5. Machine Learning & SHAP",
        "6. Live Severity Prediction Tool",
        "7. Policy Findings & Limitations"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info(
    "**Study Area:** Greater Chennai, India\n\n"
    "**Data Sources:** Greater Chennai Police annual aggregates (1998–2025), NASA POWER daily meteorology, and OpenStreetMap infrastructure. Event-level modeling data is generated."
)

# -------------------------------------------------------------
# Section 1: Executive Overview & Trends
# -------------------------------------------------------------
if nav == "Research Workflow: Preparation to Evaluation":
    render_research_workflow()

elif nav == "1. Executive Overview & Trends":
    st.title("Beyond Accident Counts: Chennai Road Safety Research")
    st.markdown("### Longitudinal Investigation of Road Crash Volume and Severity Progression (1998–2025)")

    col1, col2, col3, col4 = st.columns(4)
    row_latest = annual_df.iloc[-1]
    row_2021 = annual_df[annual_df["year"] == 2021].iloc[0]

    col1.metric("2021 Total Accidents", f"{int(row_2021['total_accidents']):,}")
    col2.metric("2021 Fatal Deaths", f"{int(row_2021['fatal_killed']):,}")
    col3.metric("Severity Rate (Fatal+Grievous)", f"{row_2021['severity_rate']:.1%}")
    col4.metric("Total Casualties", f"{int(row_2021['total_casualties']):,}")

    st.markdown("---")

    # Time series Plotly figure
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=annual_df["year"], y=annual_df["total_accidents"],
                             mode="lines+markers", name="Total Accidents", line=dict(color="#1f77b4", width=3)))
    fig.add_trace(go.Scatter(x=annual_df["year"], y=annual_df["severe_accidents"],
                             mode="lines+markers", name="Severe Crashes (Fatal+Grievous)", line=dict(color="#d62728", width=3)))
    fig.add_trace(go.Scatter(x=annual_df["year"], y=annual_df["fatal_accidents"],
                             mode="lines+markers", name="Fatal Accidents", line=dict(color="#ff7f0e", width=2, dash="dash")))

    fig.update_layout(
        title="Historical Progression of Road Accidents in Chennai (1998–2025)",
        xaxis_title="Reporting Year",
        yaxis_title="Annual Accident Count",
        hovermode="x unified",
        template="plotly_white",
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    > **Key Empirical Discovery:**
    > Between 2013 and 2021, total recorded crashes decreased from **9,710 to 5,035 (-48.1%)**.
    > However, the **severity rate (proportion of crashes causing death or grievous injury)** climbed from ~20% in the early 2000s to over **68.0%** in 2021.
    > Evaluating road safety purely by crash counts obscures worsening injury outcomes among those crashes that do occur.
    """)

# -------------------------------------------------------------
# Section 2: Severity & Infrastructure Risk
# -------------------------------------------------------------
elif nav == "2. Severity & Infrastructure Risk":
    st.title("Accident Severity and Infrastructure Risk Factors")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Severity by Vehicle Category")
        v_agg = modeling_df.groupby("vehicle_type")["severe_accident"].agg(
            total="count",
            severity_rate="mean"
        ).reset_index()
        v_agg["severity_rate_pct"] = (v_agg["severity_rate"] * 100).round(1)
        v_agg = v_agg.sort_values("severity_rate_pct", ascending=True)

        fig_v = px.bar(v_agg, y="vehicle_type", x="severity_rate_pct", orientation="h",
                       color="severity_rate_pct", color_continuous_scale="Reds",
                       labels={"vehicle_type": "Vehicle Type", "severity_rate_pct": "Severity Rate (%)"},
                       title="Severe Crash Rate (%) Across Vehicle Categories")
        st.plotly_chart(fig_v, use_container_width=True)

    with col_b:
        st.subheader("Severity by Junction Geometry")
        j_agg = modeling_df.groupby("junction_type")["severe_accident"].agg(
            total="count",
            severity_rate="mean"
        ).reset_index()
        j_agg["severity_rate_pct"] = (j_agg["severity_rate"] * 100).round(1)
        j_agg = j_agg.sort_values("severity_rate_pct", ascending=True)

        fig_j = px.bar(j_agg, y="junction_type", x="severity_rate_pct", orientation="h",
                       color="severity_rate_pct", color_continuous_scale="Purples",
                       labels={"junction_type": "Junction Type", "severity_rate_pct": "Severity Rate (%)"},
                       title="Severe Crash Rate (%) Across Road Geometries")
        st.plotly_chart(fig_j, use_container_width=True)

    st.subheader("Multivariable Logistic Regression Odds Ratios (Statistical Baseline)")
    st.dataframe(odds_ratios_df, use_container_width=True)

# -------------------------------------------------------------
# Section 3: Weather & Environmental Exposure
# -------------------------------------------------------------
elif nav == "3. Weather & Environmental Exposure":
    st.title("Atmospheric & Meteorological Coupling (NASA POWER)")

    st.markdown("Daily weather observations (2018–2023; 2,191 days) matched to Chennai geographic center (13.0827°N, 80.2707°E).")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Rainfall Intensity vs. Crash Severity")
        r_agg = modeling_df.groupby("rainfall_category")["severe_accident"].agg(
            total="count",
            severity_rate="mean"
        ).reset_index()
        r_agg["severity_rate_pct"] = (r_agg["severity_rate"] * 100).round(1)

        fig_r = px.bar(r_agg, x="rainfall_category", y="severity_rate_pct",
                       color="severity_rate_pct", color_continuous_scale="Blues",
                       labels={"rainfall_category": "Rainfall Intensity", "severity_rate_pct": "Severity Rate (%)"},
                       title="Severity Rate Across Rainfall Regimes")
        st.plotly_chart(fig_r, use_container_width=True)

    with col2:
        st.subheader("Ambient Lighting Conditions")
        l_agg = modeling_df.groupby("lighting_condition")["severe_accident"].agg(
            total="count",
            severity_rate="mean"
        ).reset_index()
        l_agg["severity_rate_pct"] = (l_agg["severity_rate"] * 100).round(1)

        fig_l = px.bar(l_agg, x="lighting_condition", y="severity_rate_pct",
                       color="severity_rate_pct", color_continuous_scale="Teal",
                       labels={"lighting_condition": "Lighting", "severity_rate_pct": "Severity Rate (%)"},
                       title="Severity Rate Across Lighting Conditions")
        st.plotly_chart(fig_l, use_container_width=True)

# -------------------------------------------------------------
# Section 4: Interactive Geospatial Hotspots
# -------------------------------------------------------------
elif nav == "4. Interactive Geospatial Hotspots":
    st.title("Chennai Accident Concentration Hotspots (DBSCAN & KDE)")
    st.markdown("""
    > [!NOTE]
    > **Illustrative map:** Coordinates come from generated event-like records, not observed crash locations. These clusters do not establish real crash hotspots or traffic-normalized risk.
    """)

    st.subheader("Identified Spatial Clusters Summary (DBSCAN eps=0.75km, min_samples=40)")
    st.dataframe(hotspots_df, use_container_width=True)

    st.subheader("Interactive GIS Map (OpenStreetMap & Folium)")
    html_map_path = MAPS_DIR / "chennai_accident_hotspots_interactive_map.html"
    if html_map_path.exists():
        with open(html_map_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        st.components.v1.html(html_content, height=650)
    else:
        st.warning("Interactive map HTML artifact not found. Please run geospatial pipeline.")

# -------------------------------------------------------------
# Section 5: Machine Learning & SHAP
# -------------------------------------------------------------
elif nav == "5. Machine Learning & SHAP":
    st.title("Supervised Machine Learning Model Benchmarks")

    st.markdown("Performance evaluated on an independent stratified holdout split (N = 1,007 generated event-like rows).")
    st.dataframe(model_comp_df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("ROC Curves")
        roc_img = VIS_DIR / "model_eval_01_roc_curves.png"
        if roc_img.exists():
            st.image(str(roc_img), use_column_width=True)

    with col2:
        st.subheader("Confusion Matrices")
        cm_img = VIS_DIR / "model_eval_03_confusion_matrices.png"
        if cm_img.exists():
            st.image(str(cm_img), use_column_width=True)

    st.markdown("---")
    st.subheader("Model Interpretability via SHAP (XGBoost Classifier)")
    shap_img = VIS_DIR / "model_eval_05_shap_summary.png"
    if shap_img.exists():
        st.image(str(shap_img), use_column_width=True)

# -------------------------------------------------------------
# Section 6: Live Severity Prediction Tool
# -------------------------------------------------------------
elif nav == "6. Live Severity Prediction Tool":
    st.title("Real-Time Accident Severity Prediction Simulator")
    st.markdown("Interactively configure pre-crash conditions to estimate the probability of severe injury outcomes.")

    col1, col2, col3 = st.columns(3)
    with col1:
        v_type = st.selectbox("Involved Vehicle Category", ["Two-Wheeler", "Truck/Lorry", "Bus", "Car/Jeep/Taxi", "Auto-rickshaw", "Pedestrian/Bicycle"])
        acc_hour = st.slider("Hour of Day (Chennai local time, 24-hr)", 0, 23, 14)
        lighting_options = []
        if 6 <= acc_hour <= 18:
            lighting_options.append("Daylight")
        if acc_hour in (5, 6, 17, 18, 19):
            lighting_options.append("Dusk/Dawn")
        if acc_hour <= 5 or acc_hour >= 18:
            lighting_options.extend(["Night - Dark / Poor Lighting", "Night - Streetlights Lit"])
        light_cond = st.selectbox("Lighting Condition", lighting_options)
        st.caption(
            "Lighting choices follow approximate Chennai local-time windows. "
            "Daylight is limited to 18:00 or earlier; dusk/dawn and night choices "
            "appear around the transition hours. Actual sunrise and sunset vary by date."
        )
        road_class = st.selectbox("Road Classification", ["Primary Arterial", "Trunk Highway / Express Corridor", "Secondary Road", "Local / Residential"])

    with col2:
        junc_type = st.selectbox("Junction / Geometric Design", ["Mid-block / Straight Road", "T-Junction", "Four-arm Cross", "Bridge/Flyover", "Roundabout"])
        rain_cat = st.selectbox("Weather Condition", ["No Rain", "Moderate Rain", "Heavy Rain", "Very Light"])

    with col3:
        speed_lim = st.slider("Posted Speed Limit (km/h)", 30, 80, 50)
        dist_junc = st.slider("Distance to Nearest Junction (km)", 0.0, 5.0, 1.2, step=0.1)
        is_wknd = st.checkbox("Weekend (Saturday / Sunday)", value=False)

    if st.button("Predict Accident Severity Probability", type="primary"):
        # Load preprocessor and model
        try:
            preprocessor = joblib.load(MODELS_DIR / "preprocessor.joblib")
            model = joblib.load(MODELS_DIR / "xgboost_pipeline.joblib")

            # Engineer single row
            input_dict = {
                "accident_hour": acc_hour,
                "speed_limit_kmh": speed_lim,
                "distance_to_nearest_junction_km": dist_junc,
                "rainfall_mm": 20.0 if rain_cat == "Heavy Rain" else (5.0 if rain_cat == "Moderate Rain" else 0.0),
                "temp_mean_c": 28.5,
                "relative_humidity_pct": 75.0,
                "wind_speed_ms": 3.2,
                "hour_sin": np.sin(2 * np.pi * acc_hour / 24.0),
                "hour_cos": np.cos(2 * np.pi * acc_hour / 24.0),
                "month_sin": np.sin(2 * np.pi * 7 / 12.0),
                "month_cos": np.cos(2 * np.pi * 7 / 12.0),
                "dow_sin": np.sin(2 * np.pi * (6 if is_wknd else 2) / 7.0),
                "dow_cos": np.cos(2 * np.pi * (6 if is_wknd else 2) / 7.0),
                "speed_junction_exposure": speed_lim / (1.0 + dist_junc),
                "is_weekend": 1 if is_wknd else 0,
                "is_peak_hour": 1 if acc_hour in [8, 9, 10, 17, 18, 19, 20] else 0,
                "is_night": 1 if (acc_hour >= 20 or acc_hour <= 5) else 0,
                "is_late_night": 1 if acc_hour in [23, 0, 1, 2, 3, 4] else 0,
                "is_rainy_day": 1 if rain_cat != "No Rain" else 0,
                "is_unlit_darkness": 1 if light_cond == "Night - Dark / Poor Lighting" else 0,
                "night_heavy_vehicle": 1 if (acc_hour >= 20 or acc_hour <= 5) and (v_type in ["Truck/Lorry", "Bus"]) else 0,
                "wet_road_junction": 1 if (rain_cat != "No Rain") and (junc_type != "Mid-block / Straight Road") else 0,
                "is_vulnerable_user": 1 if v_type in ["Two-Wheeler", "Pedestrian/Bicycle"] else 0,
                "vehicle_type": v_type,
                "junction_type": junc_type,
                "lighting_condition": light_cond,
                "road_classification": road_class,
                "season": "Northeast Monsoon" if rain_cat != "No Rain" else "Summer",
                "rainfall_category": rain_cat
            }
            row_df = pd.DataFrame([input_dict])

            # Predict probability
            prob_severe = model.predict_proba(row_df)[0, 1]

            st.markdown("---")
            res_col1, res_col2 = st.columns([1, 2])
            with res_col1:
                if prob_severe >= 0.65:
                    st.error(f"### Predicted Outcome:\n**HIGH SEVERITY RISK**\n({prob_severe:.1%} Probability of Fatal/Grievous Injury)")
                elif prob_severe >= 0.50:
                    st.warning(f"### Predicted Outcome:\n**MODERATE SEVERITY RISK**\n({prob_severe:.1%} Probability of Fatal/Grievous Injury)")
                else:
                    st.success(f"### Predicted Outcome:\n**LOW SEVERITY / MINOR INJURY**\n({prob_severe:.1%} Probability of Fatal/Grievous Injury)")

            with res_col2:
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=prob_severe * 100,
                    domain={"x": [0, 1], "y": [0, 1]},
                    title={"text": "Estimated Severity Probability (%)"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": "#d62728" if prob_severe >= 0.65 else "#1f77b4"},
                        "steps": [
                            {"range": [0, 50], "color": "#d9f0d3"},
                            {"range": [50, 70], "color": "#fee08b"},
                            {"range": [70, 100], "color": "#fdae61"}
                        ]
                    }
                ))
                fig_gauge.update_layout(height=280, margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_gauge, use_container_width=True)

        except Exception as e:
            st.error(f"Inference error: {e}")

# -------------------------------------------------------------
# Section 7: Policy Findings & Limitations
# -------------------------------------------------------------
elif nav == "7. Policy Findings & Limitations":
    st.title("Policy Considerations & Research Limitations")

    st.subheader("Questions to test with verified crash-level data")
    st.markdown("""
    The project’s generated event-level records can suggest topics for future investigation, but they cannot establish which factors increase real crash severity. With authentic incident records, a follow-up study could examine:

    1. Whether lighting conditions are associated with injury severity after accounting for time and road context.
    2. How vehicle type, speed environment, and junction design relate to observed outcomes.
    3. Whether weather and location patterns persist when matched to individual crash records.

    These are research questions, not findings or recommendations from the current synthetic classifier.
    """)

    st.markdown("---")
    st.subheader("Scientific Research Limitations")
    st.markdown("""
    - **Annual aggregate source:** The official crash table has yearly totals and severity counts, not one row per crash, so it cannot train or validate an individual crash-severity model.
    - **Generated event-level records:** The legacy severity, weather-linkage, and hotspot analyses use constructed records. Their metrics and patterns are illustrative, not empirical Chennai crash findings.
    - **Missing exposure data:** The project does not have a complete traffic-volume denominator for comparing risk per vehicle-kilometer.
    - **Data needed next:** A defensible crash-level study needs documented incident records with observed severity, timestamps, locations, and relevant recorded conditions, plus suitable traffic-exposure data.
    """)

    st.markdown("---")
    st.warning(
        "Data integrity notice: event-level analyses in this project use generated/synthetic records, "
        "not observed individual crashes. Treat severity associations, model metrics, SHAP results, and "
        "hotspot outputs as illustrative only. The official crash source available here contains annual "
        "aggregate data. See DATA_INTEGRITY_NOTICE.md."
    )
