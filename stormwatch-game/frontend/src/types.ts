export type MapCell = {
  x: number;
  y: number;
  terrain_type: 'river' | 'canal' | 'road' | 'building' | 'grass' | 'park';
  elevation_mm: number;
  impervious_ratio: number;
  infiltration_rate_mm_hr: number;
  drainage_capacity_mm_hr: number;
  building_id: string | null;
  district_id: string;
  can_water_flow: boolean;
  is_road: boolean;
  is_bridge: boolean;
  interactive_object_id?: string;
  water_depth_mm: number;
  rainfall_intensity_mm_hr: number;
  flood_risk_index: number;
  predicted_water_depth_mm: number;
  pump_capacity_mm_hr: number;
};

export type CityLocation = {
  id: string;
  name: string;
  kind: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type EastbankMap = {
  map_id: string;
  name: string;
  columns: number;
  rows: number;
  tile_size_px: number;
  pixel_width: number;
  pixel_height: number;
  seed: number;
  layers: string[];
  locations: CityLocation[];
  cells: MapCell[];
  rainfall_mm_per_hour: number;
  weather_observations: WeatherObservation[];
  budget_credits: number;
  available_resources: Resource[];
};

export type SessionResourceState = {
  budget_initial_credits: number;
  budget_remaining_credits: number;
  inventory: { barriers: number; pumps: number; rescue_boats: number };
  barriers: Array<{ position: { x: number; y: number }; direction: 'N' | 'E' | 'S' | 'W'; height_mm: number; deployment_cost: number }>;
  pumps: Array<{ grid_position: { x: number; y: number }; drainage_capacity_mm_hr: number; operating_radius_cells: number; deployment_cost: number }>;
  rescue_boats: Array<{ grid_position: { x: number; y: number }; deployment_cost: number; operating_radius_cells: number; evacuation_capacity: number }>;
};

export type MissionState = {
  mission_id: string;
  title: string;
  objectives: Record<string, boolean>;
  completed_count: number;
  total_count: number;
};

export type GameState = EastbankMap & {
  session_id: string;
  elapsed_minutes: number;
  elapsed_seconds: number;
  timestep_minutes: number;
  historical_observation_count: number;
  historical_observations?: AnalyticsObservation[];
  resources: SessionResourceState;
  simulation: {
    timestep_minutes: number;
    dt_hours: number;
    elapsed_minutes: number;
    elapsed_seconds: number;
    maximum_water_depth_mm: number;
    average_water_depth_mm: number;
    flooded_road_count: number;
    hospital_access_status: string;
    location_accessibility: Record<string, string>;
    water_volume_balance: Record<string, number | boolean | string>;
    resources: SessionResourceState;
  };
  mission_state: MissionState;
  scenario_progress: {
    started: boolean;
    active: boolean;
    complete: boolean;
    step: number;
    total_steps: number;
    next_rainfall_mm_hr: number | null;
  };
  prediction_model_results: Record<string, unknown>;
  response_outcome: {
    total_flooded_cells: number;
    flooded_road_count: number;
    hospital_access: string;
    school_access: string;
    residential_locations: Array<{ id: string; name: string; x: number; y: number; residents: number; maximum_water_depth_mm: number; at_risk: boolean; evacuated: boolean }>;
    residential_locations_at_risk: number;
    residents_evacuated: number;
    remaining_water_depth_mm: number;
    pump_water_removed_m3: number;
    remaining_budget_credits: number;
    score: number;
    score_breakdown: Record<string, number>;
    ending: string | null;
    finalized: boolean;
  };
};

export type WeatherObservation = {
  station_id: string;
  name: string;
  rainfall_mm_hr: number;
  wind_kmh: number;
  air_pressure_hpa: number;
};

export type Resource = { id: string; name: string; count: number; cost: number };

export type AnalyticsObservation = {
  timestamp: string;
  station_id: string;
  rainfall_mm_hr: number;
  temperature_c: number;
  humidity_pct: number;
  wind_speed_kmh: number;
  pressure_hpa: number;
  water_depth_mm: number;
};

export type AnalyticsMetric = { mae: number; rmse: number };

export type PredictionLabData = {
  station: { station_id: string; name: string };
  seed: number;
  window_size: number;
  split: { method: string; training_count: number; heldout_count: number; training_cutoff: string };
  regression: {
    slope: number;
    intercept: number;
    prediction_line: { x: [number, number]; y: [number, number] };
    model_name: string;
    input_feature: string;
    target: string;
    training_count: number;
  };
  training_observations: AnalyticsObservation[];
  heldout_observations: AnalyticsObservation[];
  moving_average?: { values_mm: number[]; timestamps: string[] };
  evaluation: {
    sample_count: number;
    moving_average: { metrics: AnalyticsMetric; predictions_mm: number[] };
    linear_regression: { metrics: AnalyticsMetric; predictions_mm: number[] };
  };
  correlations: Record<string, { label: string; coefficient: number | null; sample_count: number; explanation: string }>;
  descriptive_statistics?: {
    rainfall_mm_hr: Record<string, number>;
    water_depth_mm: Record<string, number>;
  };
  educational_note: string;
};

export type ForecastResult = {
  station: { station_id: string; name: string };
  predictions: Array<{
    prediction_time: string;
    rainfall_mm_hr: number;
    predicted_value_mm: number;
    moving_average_baseline_mm: number;
  }>;
  model_information: { name: string; slope: number; intercept: number; training_count: number; training_cutoff: string };
};
export type FloodOverlay = 'elevation' | 'rainfall' | 'water' | 'drainage' | 'risk' | null;
