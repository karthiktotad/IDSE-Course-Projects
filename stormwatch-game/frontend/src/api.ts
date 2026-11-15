import type {
  AnalyticsObservation,
  EastbankMap,
  ForecastResult,
  GameState,
  PredictionLabData,
  SessionResourceState,
} from './types';

const API_ROOT = '/api';

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = 'ApiError';
  }
  get isNetworkFailure() { return this.status === undefined; }
  get isInvalidSession() { return this.status === 404 && /session/i.test(this.message); }
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : 'Network request failed';
    throw new ApiError(`Python service is unreachable: ${reason}`);
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json() as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
      else if (body.detail !== undefined) detail = JSON.stringify(body.detail);
    } catch {
      const body = await response.text().catch(() => '');
      if (body) detail = body;
    }
    throw new ApiError(detail, response.status);
  }
  try {
    return await response.json() as T;
  } catch {
    throw new ApiError(`Python service returned invalid JSON for ${path}`, response.status);
  }
}

const jsonBody = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) });

export const health = () => requestJson<{ status: string; service: string }>('/health');

export function newGame(seed = 2406): Promise<GameState> {
  return requestJson<GameState>('/game/new', jsonBody({ seed }));
}

export function getGameState(sessionId: string): Promise<GameState> {
  return requestJson<GameState>(`/game/${encodeURIComponent(sessionId)}/state`);
}

export function setRainfall(sessionId: string, rainfallIntensityMmHr: number): Promise<GameState> {
  return requestJson<GameState>(`/game/${encodeURIComponent(sessionId)}/rainfall`, jsonBody({ rainfall_intensity_mm_hr: rainfallIntensityMmHr }));
}

export function advanceGame(sessionId: string, steps = 1): Promise<GameState> {
  return requestJson<GameState>(`/game/${encodeURIComponent(sessionId)}/advance`, jsonBody({ steps }));
}

export function startFloodScenario(sessionId: string): Promise<GameState> {
  return requestJson<GameState>(`/game/${encodeURIComponent(sessionId)}/scenario/start`, { method: 'POST' });
}

export type PlaceResourceInput = {
  resource_type: 'pump' | 'barrier' | 'rescue-boat';
  x: number;
  y: number;
  direction?: 'N' | 'E' | 'S' | 'W';
};

export function placeResource(sessionId: string, placement: PlaceResourceInput): Promise<GameState> {
  return requestJson<GameState>(`/game/${encodeURIComponent(sessionId)}/place-resource`, jsonBody(placement));
}

export function identifyRisk(sessionId: string, x: number, y: number): Promise<GameState> {
  return requestJson<GameState>(`/game/${encodeURIComponent(sessionId)}/identify-risk`, jsonBody({ x, y }));
}

export function resetGame(sessionId: string): Promise<GameState> {
  return requestJson<GameState>(`/game/${encodeURIComponent(sessionId)}/reset`, { method: 'POST' });
}

export function reportMissionObjective(sessionId: string, objectiveId: string): Promise<GameState> {
  return requestJson<GameState>(`/game/${encodeURIComponent(sessionId)}/mission/objective`, jsonBody({ objective_id: objectiveId }));
}

export type StatisticsResponse = {
  mean: number;
  median: number;
  minimum: number;
  maximum: number;
  standard_deviation: number;
  count: number;
  sum: number;
};
export function calculateStatistics(values: number[], sessionId?: string): Promise<StatisticsResponse> {
  return requestJson('/analytics/statistics', jsonBody({ values, session_id: sessionId }));
}

export type MovingAverageResponse = { values: number[]; timestamps: string[] };
export function calculateMovingAverage(
  data: number[], windowSize: number, timestamps?: string[], sessionId?: string,
): Promise<MovingAverageResponse> {
  return requestJson('/analytics/moving-average', jsonBody({ data, window_size: windowSize, timestamps, session_id: sessionId }));
}

export type RegressionResponse = {
  slope: number;
  intercept: number;
  fitted_predictions: number[];
  residuals: number[];
  prediction_line: { x: [number, number]; y: [number, number] };
  train_count: number;
  test_count: number;
  train_x: number[];
  train_y: number[];
  test_x: number[];
  test_y: number[];
  test_predictions: number[];
  training_cutoff_index: number;
  split_method: string;
  manual_line?: {
    slope: number;
    intercept: number;
    endpoint_x: [number, number];
    endpoint_y: [number, number];
    fitted_predictions: number[];
    residuals: number[];
    mae: number;
  };
};
export function fitRegression(
  x: number[], y: number[], sessionId?: string,
  manualLine?: { x: [number, number]; y: [number, number] },
): Promise<RegressionResponse> {
  return requestJson('/analytics/regression', jsonBody({
    x, y, test_fraction: 0.2, session_id: sessionId,
    ...(manualLine ? { manual_line_x: manualLine.x, manual_line_y: manualLine.y } : {}),
  }));
}

export type CorrelationResponse = {
  x_label: string;
  y_label: string;
  coefficient: number | null;
  sample_count: number;
  explanation: string;
};
export function calculateCorrelation(
  x: number[], y: number[], xLabel: string, yLabel: string, sessionId?: string,
): Promise<CorrelationResponse> {
  return requestJson('/analytics/correlation', jsonBody({ x, y, x_label: xLabel, y_label: yLabel, session_id: sessionId }));
}

export type EvaluationResponse = {
  sample_count: number;
  timestamps: string[] | null;
  moving_average: { metrics: { mae: number; rmse: number }; predictions: number[] };
  linear_regression: { metrics: { mae: number; rmse: number }; predictions: number[] };
};
export function evaluateModels(
  actual: number[], movingAveragePredictions: number[], regressionPredictions: number[], timestamps: string[], sessionId?: string,
): Promise<EvaluationResponse> {
  return requestJson('/analytics/evaluate', jsonBody({
    actual,
    moving_average_predictions: movingAveragePredictions,
    regression_predictions: regressionPredictions,
    timestamps,
    session_id: sessionId,
  }));
}

export function forecast(
  sessionId: string, stationId: string, rainfallObservations: number[], seed: number, windowSize: number,
): Promise<ForecastResult> {
  return requestJson('/analytics/forecast', jsonBody({
    session_id: sessionId,
    station_id: stationId,
    rainfall_observations: rainfallObservations,
    seed,
    window_size: windowSize,
  }));
}

export async function buildPredictionLab(
  state: GameState,
  stationId: string,
  windowSize: number,
): Promise<PredictionLabData> {
  const observations = (state.historical_observations ?? [])
    .filter(row => row.station_id === stationId)
    .slice()
    .sort((left, right) => left.timestamp.localeCompare(right.timestamp));
  if (observations.length < 2) throw new ApiError('This game session has no historical station observations. Start a new game.');
  const rainfall = observations.map(row => row.rainfall_mm_hr);
  const depth = observations.map(row => row.water_depth_mm);
  const timestamps = observations.map(row => row.timestamp);
  const [rainStats, waterStats, model, average, rainWater, temperatureHumidity, pressureWind, rainHumidity] = await Promise.all([
    calculateStatistics(rainfall, state.session_id),
    calculateStatistics(depth, state.session_id),
    fitRegression(rainfall, depth, state.session_id),
    calculateMovingAverage(depth, windowSize, timestamps, state.session_id),
    calculateCorrelation(rainfall, depth, 'Rainfall', 'Water depth', state.session_id),
    calculateCorrelation(observations.map(row => row.temperature_c), observations.map(row => row.humidity_pct), 'Temperature', 'Humidity', state.session_id),
    calculateCorrelation(observations.map(row => row.pressure_hpa), observations.map(row => row.wind_speed_kmh), 'Pressure', 'Wind speed', state.session_id),
    calculateCorrelation(rainfall, observations.map(row => row.humidity_pct), 'Rainfall', 'Humidity', state.session_id),
  ]);
  const training = observations.slice(0, model.train_count);
  const heldout = observations.slice(model.train_count);
  const baselineStart = model.train_count - windowSize;
  const baseline = heldout.map((_, index) => average.values[baselineStart + index]);
  const evaluation = await evaluateModels(
    heldout.map(row => row.water_depth_mm),
    baseline,
    model.test_predictions,
    heldout.map(row => row.timestamp),
    state.session_id,
  );
  const correlations = [rainWater, temperatureHumidity, pressureWind, rainHumidity];
  const correlationKeys = ['rainfall_water_depth', 'temperature_humidity', 'pressure_wind_speed', 'rainfall_humidity'];
  const stationName = state.locations.find(location => location.id === stationId)?.name ?? stationId;
  return {
    station: { station_id: stationId, name: stationName },
    seed: state.seed,
    window_size: windowSize,
    split: {
      method: model.split_method,
      test_fraction: model.test_count / observations.length,
      training_count: model.train_count,
      heldout_count: model.test_count,
      training_cutoff: training[training.length - 1]?.timestamp ?? '',
    },
    descriptive_statistics: { rainfall_mm_hr: rainStats, water_depth_mm: waterStats },
    regression: {
      slope: model.slope,
      intercept: model.intercept,
      prediction_line: model.prediction_line,
      model_name: 'Rainfall linear regression',
      input_feature: 'rainfall_mm_hr',
      target: 'water_depth_mm',
      training_count: model.train_count,
    },
    training_observations: training,
    heldout_observations: heldout,
    moving_average: { values_mm: average.values, timestamps: average.timestamps },
    evaluation: {
      sample_count: evaluation.sample_count,
      timestamps: evaluation.timestamps ?? [],
      moving_average: { metrics: evaluation.moving_average.metrics, predictions_mm: evaluation.moving_average.predictions },
      linear_regression: { metrics: evaluation.linear_regression.metrics, predictions_mm: evaluation.linear_regression.predictions },
    },
    correlations: Object.fromEntries(correlations.map((item, index) => [correlationKeys[index], {
      label: `${item.x_label} and ${item.y_label}`,
      coefficient: item.coefficient,
      sample_count: item.sample_count,
      explanation: item.explanation,
    }])),
    educational_note: 'Regression uses the chronological training observations. Both metrics use the same unseen timestamps. Correlation does not establish causation.',
  } as PredictionLabData;
}

export type { AnalyticsObservation, EastbankMap, GameState, SessionResourceState };
