# Data Integrity Notice

**Updated:** 2026-11-14

## What the data supports

The OpenCity / Greater Chennai Police crash file in `data/raw/accidents/chennai_road_crashes_1998_2025.csv` contains annual aggregate severity counts. It does not contain one record per crash, incident timestamps, or crash coordinates. The weather and OpenStreetMap files are separate source datasets and are not linked observations of individual crashes.

## What the event-level results represent

`data/processed/chennai_accident_severity_modeling_dataset.csv` contains 5,035 generated event-level rows calibrated to 2021 aggregate totals and other marginal distributions. These rows are synthetic; they are not observed individual crash records. The saved feature matrix, models, predictions, metrics, plots, hotspot results, dashboard analyses, and reports derived from those rows are therefore illustrative outputs, not empirical findings about crash-level patterns in Chennai.

In particular, the repository's event-level severity associations, weather and infrastructure comparisons, classifier scores, SHAP explanations, and crash hotspot locations must not be interpreted as measured local effects or used to guide policy. The annual source aggregates can support aggregate trend descriptions, subject to the source documentation and known data limitations.

Some historical reports, notebooks, and original dashboard pages still describe generated results as empirical. This notice supersedes those descriptions. The added **Research Workflow: Preparation to Evaluation** dashboard section and the final report use only the official annual aggregate source for empirical findings. A valid crash-level analysis requires genuine incident-level records with documented provenance and appropriate location/time fields, followed by recomputation of every derived result.

## Reproducibility status

The legacy collection and event-level analysis pipeline has not been verified end to end; its collection runner has a known method-name mismatch. The new aggregate workflow can be rebuilt with `python main.py --stage report` or `python scripts/build_aggregate_report.py`. It validates the annual source, prepares derived fields, creates EDA and forecast outputs, and evaluates rolling-origin and final chronological holdout predictions.

The final report at `reports/FINAL_RESEARCH_REPORT.md` and the added dashboard workflow use only the official annual aggregate crash table. Their annual features, forecast comparisons, metrics, and figures can be regenerated with the commands above; this analysis does not use the generated event-level dataset or the saved synthetic models.
