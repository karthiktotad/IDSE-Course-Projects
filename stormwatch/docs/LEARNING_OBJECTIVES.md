# Learning Objectives

After completing the Eastbank scenario, a player should be able to:

1. **Summarize observations:** calculate and interpret a mean, median, range and population standard deviation for rainfall readings.
2. **Recognize a trend:** compare raw rainfall to trailing moving averages, and explain how window size trades short-term responsiveness for smoothing.
3. **Interpret a fitted line:** explain slope and intercept in the rainfall-to-water-depth model, relate residuals to prediction error, and make a prediction from a chosen rainfall value.
4. **Evaluate forecasts:** use chronological unseen observations and compare MAE and RMSE for a moving-average baseline and linear regression on the same timestamps.
5. **Interpret association carefully:** describe Pearson correlation and distinguish association from causation.
6. **Connect data to place:** use elevation, impervious surface, drainage and observed water depth to identify vulnerable locations on the map.
7. **Make constrained decisions:** allocate a finite response budget, anticipate access and evacuation consequences, and evaluate the resulting city condition.

## Evidence in play

| Objective | Player action | Visible evidence |
|---|---|---|
| Summarize | Inspect station readings and calculate their average | Rainfall series and returned descriptive statistics |
| Smooth | Change the moving-average window | Raw and smoothed lines with updated values |
| Fit | Drag a line, inspect residuals, then request best fit | Scatter plot, residual distances, slope and intercept |
| Evaluate | Compare models | Same held-out timestamps with MAE and RMSE |
| Associate | Select weather-variable pairs | Pearson coefficient and correlation caveat |
| Map risk | Toggle overlays and inspect cells | Elevation, rainfall, depth, drains and flood-risk values |
| Allocate | Preview and confirm resources | Placement validation, budget change, and altered final metrics |

The synthetic observations are designed for experimentation. The scenario does not certify real-world flood forecasting skill.
