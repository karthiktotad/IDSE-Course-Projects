# STORMWATCH weather analytics and forecasts

The local analytics implementation lives in `backend/app/analytics/`. Python and NumPy generate the observations, calculate statistics, fit the models and produce forecasts. The Phaser client displays returned training, holdout and forecast values; it does not calculate flood depth or regression coefficients.

## Reproducible synthetic weather

`weather_generator.py` reads the four weather station locations from `shared/eastbank_grid.json`. A configurable NumPy random seed controls gauge noise and atmospheric variation. Historical output contains four synthetic storm events by default, sampled every ten minutes, followed by a separate multi-pulse Eastbank watch scenario. The output record includes timestamp, station ID, rainfall, temperature, humidity, wind speed, pressure and observed water depth.

Rainfall has shared storm pulses with station-specific scales and spatially related noise. Atmospheric values respond to storm intensity and use changing regimes, so the relationships vary between events. For water-depth observations, station rainfall is inverse-distance interpolated across the map. Every timestep then calls the existing flood engine's rainfall, infiltration, drainage and simultaneous water-flow functions. Each event starts with a dry grid. This makes water levels respond to rain and Eastbank's authored terrain, drainage and flow paths rather than to unrelated random samples.

The generated storms are educational synthetic data, not recorded weather. They do not represent a calibrated meteorological or hydrologic forecast.

## Analysis and models

- Descriptive standard deviation is the population statistic (`ddof=0`). Inputs must be finite, non-empty one-dimensional numeric series.
- Moving averages are trailing means. A result is timestamped at the end of its window; a numeric series without labels uses its end index.
- Regression fits `water_depth_mm = slope × rainfall_mm_hr + intercept` by NumPy least squares. The prediction lab fits on the first 80% of observations in chronological order. The displayed line coordinates and future forecasts use the same coefficients. With constant rainfall input, the safe least-squares solution is a constant prediction at mean training depth.
- The final 20% is held out for evaluation. MAE and RMSE are calculated for both models on those same timestamps. The moving-average comparison is rolling one-step-ahead: a held-out step can use previously observed depths, including earlier steps in the held-out period. The future moving-average forecast instead repeats the mean of the latest observed window because future depths are not known.
- The future regression estimate is the raw model equation output and may be negative or implausible when extrapolating. The lab displays the model's observations and equation so the player can inspect that limitation.
- Pearson correlation is undefined for a constant series and is returned as `null`. It describes linear association; correlation does not establish causation.

Rainfall-only regression deliberately omits antecedent water level, time lag, tide, soil state, infrastructure actions and other predictors. It teaches fitting and evaluating a simple model, not operational flood prediction.

## Local API

- `GET /api/analytics/weather?seed=2406` returns station metadata, historical event observations and the separate Eastbank scenario.
- `GET /api/analytics/lab?station_id=weather-central&window_size=6` returns descriptive statistics, correlations, the chronological split, chart observations, fitted regression line and same-holdout model comparison.
- `POST /api/analytics/forecast` accepts `station_id`, a `rainfall_observations` array, and optional `seed`, `interval_minutes` and `window_size`. It returns timestamped regression predictions, the constant moving-average baseline and the model coefficients/evaluation.

Example request:

```json
{
  "station_id": "weather-central",
  "rainfall_observations": [25, 40, 55],
  "seed": 2406,
  "interval_minutes": 10,
  "window_size": 6
}
```

Start the backend with the existing Windows instructions in `README.md`; the prediction lab is available from the game's **PREDICTION** mode.
