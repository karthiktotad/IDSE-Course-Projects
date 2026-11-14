# Data Integrity Notice

**Updated:** 2026-11-14

## What the data supports

The OpenCity / Greater Chennai Police crash file in `data/raw/accidents/chennai_road_crashes_1998_2025.csv` contains annual aggregate severity counts. It does not contain one record per crash, incident timestamps, or crash coordinates. The weather and OpenStreetMap files are separate source datasets and are not linked observations of individual crashes.

## What the event-level results represent

`data/processed/chennai_accident_severity_modeling_dataset.csv` contains 5,035 generated event-level rows calibrated to 2021 aggregate totals and other marginal distributions. These rows are synthetic; they are not observed individual crash records. The saved feature matrix, models, predictions, metrics, plots, hotspot results, dashboard analyses, and reports derived from those rows are therefore illustrative outputs, not empirical findings about crash-level patterns in Chennai.

In particular, the repository's event-level severity associations, weather and infrastructure comparisons, classifier scores, SHAP explanations, and crash hotspot locations must not be interpreted as measured local effects or used to guide policy. The annual source aggregates can support aggregate trend descriptions, subject to the source documentation and known data limitations.

Some historical reports, notebooks, and saved dashboard artifacts still describe generated results as empirical. This notice supersedes those descriptions. The current research dashboard and final report use only the official annual aggregate source for empirical findings. A valid crash-level analysis requires genuine incident-level records with documented provenance and appropriate location/time fields, followed by recomputation of every derived result.

## Reproducibility status

The verified annual aggregate workflow is reproducible end to end with `python main.py --stage report` or `python scripts/build_aggregate_report.py`. It validates the source, prepares derived fields, creates EDA and forecast outputs, and evaluates rolling-origin and final chronological holdout predictions. The older multi-stage collection and event-level analysis pipeline is not part of this verified workflow and should not be treated as empirical evidence.

The final report at `reports/FINAL_RESEARCH_REPORT.md` and the current Streamlit dashboard use only the official annual aggregate crash table. Their annual features, forecast comparisons, metrics, and figures can be regenerated with the commands above; this analysis does not use the generated event-level dataset or the saved synthetic models.
