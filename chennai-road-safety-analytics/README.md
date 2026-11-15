# Chennai Road Safety Analytics

An interactive dashboard and research report exploring road-crash trends in Greater Chennai.

## Start here

**[Read the Final Research Report](reports/FINAL_RESEARCH_REPORT.md)**

**Live dashboard:** [road-safety-ml-chennai.streamlit.app](https://road-safety-ml-chennai.streamlit.app/)

## Project scope

The verified analysis uses the official Chennai crash table for **1998–2025**. It prepares and explores annual accident totals and compares simple models for forecasting the total number of accidents per year.

The source contains annual aggregate counts, not individual crash records. It does not include crash-by-crash vehicle, lighting, speed, time, or location details, so it cannot validate an individual crash-severity predictor.

## Data integrity

The dashboard also retains a severity-prediction simulator and event-level charts from earlier project work. Their 5,035 incident-like records were generated from aggregate totals and other datasets; they are **not observed individual crashes**. The classifier metrics, SHAP results, and hotspot maps are illustrative and should not be interpreted as real-world Chennai crash findings. See [DATA_INTEGRITY_NOTICE.md](DATA_INTEGRITY_NOTICE.md) for details.

## Run the dashboard

```bash
git clone https://github.com/karthiktotad/chennai-road-safety-analytics.git
cd chennai-road-safety-analytics
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Rebuild the verified analysis

```bash
python scripts/build_aggregate_report.py
```

This reads `data/raw/accidents/chennai_road_crashes_1998_2025.csv` and regenerates the aggregate analysis outputs. It does not use the generated event-level dataset.

## Key files

- [Data integrity notice](DATA_INTEGRITY_NOTICE.md)
- [Data sources](DATA_SOURCES.md)
- Dashboard: `app.py`
- Aggregate analysis builder: `scripts/build_aggregate_report.py`
