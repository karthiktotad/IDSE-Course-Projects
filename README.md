# Chennai Road Safety Analytics: Aggregate Trends and Forecast Evaluation

> [!CAUTION]
> **Data integrity notice:** The 5,035-row event-level modeling dataset and the analyses derived from it are generated/synthetic, not observed crash records. Those results are illustrative and do not support empirical claims about crash-level patterns in Chennai. The official crash source available here is annual aggregate data. See [DATA_INTEGRITY_NOTICE.md](DATA_INTEGRITY_NOTICE.md) before interpreting or reusing results.

## 1. Project Title & Overview
**Study Area:** Greater Chennai Police Commissionerate, Tamil Nadu, India  
**Primary Objective:** Describe official annual accident counts and severity composition, then evaluate simple time-ordered forecasts. The available official Chennai crash source is annual aggregate data; it cannot support incident-level risk-factor or hotspot claims.

---

## Current deliverable

- [Final research report](reports/FINAL_RESEARCH_REPORT.md): aggregate-data analysis, chronological model comparison, limitations, and rubric coverage.
- Rebuild its figures and metrics from the raw official annual table with `python scripts/build_aggregate_report.py`.
- The Streamlit dashboard (`app.py`) still contains legacy event-level demo outputs based on generated records. It displays a data-integrity warning; do not cite those outputs as empirical findings.

### Current status
- **Verified analysis path:** The aggregate report script regenerates annual summary metrics, forecast comparisons, and three report figures from the official annual CSV.
- **Not verified:** The legacy multi-stage collection/analysis pipeline. Its collection runner has a known method-name mismatch.
- **Not empirical:** Existing event-level models, hotspots, and related charts/reports derived from generated data.

---

## 3. Project Structure

```text
Chennai_Road_Accident_Research/
├── data/
│   ├── raw/                  # Immutable original raw datasets
│   │   ├── accidents/        # Chennai crash data (1998-2025 CSV, report PDF, TN benchmarks)
│   │   ├── weather/          # NASA POWER daily meteorology (2,191 daily records)
│   │   ├── road_network/     # OSM major roads (1,804 ways) & 498 junctions/signals
│   │   └── supplementary/    # Traffic police jurisdictions (KML), police stations, bridges, vehicles
│   ├── interim/              # Intermediate transformations
│   └── processed/            # Cleaned, standardized analysis datasets
│       ├── chennai_annual_crash_severity_preprocessed.csv
│       ├── tamil_nadu_district_accidents_preprocessed.csv
│       ├── chennai_daily_weather_preprocessed.csv
│       ├── chennai_osm_junctions_preprocessed.csv
│       ├── chennai_osm_roads_preprocessed.csv
│       ├── chennai_traffic_police_jurisdictions_preprocessed.csv
│       ├── chennai_police_stations_preprocessed.csv
│       ├── chennai_accident_severity_modeling_dataset.csv
│       └── chennai_feature_matrix.csv
├── notebooks/                # 9 Research notebooks (01 through 09)
│   ├── 01_data_collection.ipynb
│   ├── 02_data_inspection.ipynb
│   ├── 03_data_preprocessing.ipynb
│   ├── 04_exploratory_data_analysis.ipynb
│   ├── 05_statistical_analysis.ipynb
│   ├── 06_feature_engineering.ipynb
│   ├── 07_model_development.ipynb
│   ├── 08_model_evaluation.ipynb
│   └── 09_geospatial_analysis.ipynb
├── src/                      # Modular Python engineering codebase
│   ├── data_collection/      # Automated ingestion scripts and API clients
│   ├── preprocessing/        # Data cleaning, spatial parsing, and integration logic
│   ├── feature_engineering/  # Feature transformation pipelines
│   ├── statistical_analysis/ # Hypothesis tests & statistical diagnostics
│   ├── modeling/             # Model training pipelines & tuning
│   ├── evaluation/           # Metrics, confusion matrices, ROC/PR curves
│   └── geospatial/           # Spatial clustering (DBSCAN/KDE) and map builders
├── models/                   # Serialized pipelines (joblib) & test predictions (json)
├── results/                  # Visualizations, reports, maps, and metric tables
│   ├── visualizations/       # 12 EDA figures + 4 ML evaluation + 1 GIS map
│   ├── reports/              # Data audit, EDA findings, statistical, ML, & GIS reports
│   ├── maps/                 # Interactive Folium HTML map
│   └── metrics/              # Hotspot summaries, model tables, & hypothesis tests
├── config/                   # Centralized project configuration
├── logs/                     # Pipeline execution logs
├── reports/
│   └── FINAL_RESEARCH_REPORT.md # Comprehensive academic research monograph
├── app.py                    # Interactive Streamlit research dashboard
├── main.py                   # Master CLI execution pipeline
├── requirements.txt          # Python package dependencies
├── DATA_SOURCES.md           # Dataset attribution and metadata registry
├── PROJECT_DECISIONS.md      # Methodological and research design decisions
└── README.md                 # Primary project documentation and tracker
```

---

## 4. Manual Verification & Step-by-Step Execution Instructions

### A. Environment Activation
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### B. Rebuild the final report analysis

```bash
python scripts/build_aggregate_report.py
```

This deterministic command reads the official annual crash CSV and regenerates the final report's figures and metric tables. It does not load the synthetic event-level dataset.

### C. Legacy full pipeline

The following command is retained as historical project code. The full pipeline is not verified end to end, the collector has a known method-name mismatch, and some legacy stages produce generated event-level outputs. Do not use those outputs as empirical crash-level findings.

```bash
PYTHONPATH=. python3 main.py --stage all
```

Individual legacy stages and original notebooks remain available for inspection but do not form the evidence base of the final report.

### D. Launching the Interactive Streamlit Dashboard
```bash
streamlit run app.py
```
*Access the dashboard in your web browser at `http://localhost:8501`.*

### E. Viewing Maps & Reports
- **Interactive GIS Map:** Open `results/maps/chennai_accident_hotspots_interactive_map.html` in any web browser.
- **Final aggregate analysis report:** Read `reports/FINAL_RESEARCH_REPORT.md`.
- **Aggregate forecast metrics:** Inspect `results/metrics/annual_forecast_model_comparison.csv`.
- **Legacy event-level metrics:** These use generated data and are illustrative only.

---

## Research distinctions and integrity rules

1. **Aggregate counts vs. incident risk:** The final report analyzes annual totals. It does not estimate crash-level severity probability or incident risk.
2. **Hotspots:** Existing hotspot outputs use generated event-level rows and must not be presented as empirical Chennai crash locations.
3. **Data authenticity:** The event-level modeling dataset is synthetic and derived event-level results are illustrative only. See [DATA_INTEGRITY_NOTICE.md](DATA_INTEGRITY_NOTICE.md).
