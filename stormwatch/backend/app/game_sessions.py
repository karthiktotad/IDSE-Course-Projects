"""In-memory authoritative game sessions over independent flood engines."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from uuid import uuid4
from typing import Any

from app.analytics.weather_generator import DEFAULT_SEED, generate_weather_data
from app.simulation.flood_engine import FloodEngine


def _map_document() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "shared" / "eastbank_grid.json"
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class GameSession:
    session_id: str
    seed: int
    engine: FloodEngine
    historical_observations: tuple[dict[str, Any], ...]
    scenario_rainfall_mm_hr: tuple[float, ...]
    locations: tuple[dict[str, Any], ...]
    map_document: dict[str, Any]
    prediction_model_results: dict[str, Any] = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock, repr=False)
    objective_progress: dict[str, bool] = field(default_factory=lambda: {
        "inspect_hospital": False,
        "inspect_weather": False,
        "inspect_drainage": False,
        "review_risk": False,
        "advance_simulation": False,
        "place_resource": False,
        "build_forecast": False,
        "compare_models": False,
    })
    scenario_step: int = 0
    scenario_active: bool = False
    scenario_started: bool = False
    scenario_complete: bool = False
    identified_risk_cells: set[tuple[int, int]] = field(default_factory=set)


class GameSessionManager:
    """Owns independent game state; sessions are lost on backend restart."""

    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._lock = RLock()
        self._map = _map_document()

    def new_game(self, seed: int = DEFAULT_SEED) -> dict[str, Any]:
        weather = generate_weather_data(seed)
        scenario_by_time: dict[str, list[float]] = {}
        for observation in weather.eastbank_scenario:
            scenario_by_time.setdefault(observation.timestamp, []).append(observation.rainfall_mm_hr)
        engine = FloodEngine(seed)
        session = GameSession(
            session_id=uuid4().hex,
            seed=seed,
            engine=engine,
            historical_observations=tuple(record.to_dict() for record in weather.historical),
            scenario_rainfall_mm_hr=tuple(
                sum(values) / len(values) for _, values in sorted(scenario_by_time.items())
            ),
            locations=tuple(self._map["locations"]),
            map_document=self._map,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return self._state(session, include_history=True)

    def _require(self, session_id: str) -> GameSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Game session '{session_id}' was not found. Start a new game.")
        return session

    def validate_session(self, session_id: str) -> None:
        self._require(session_id)

    @staticmethod
    def _state(session: GameSession, include_history: bool = False) -> dict[str, Any]:
        simulation = session.engine.get_state()
        static_cells = session.map_document["cells"]
        cells = []
        for static, dynamic in zip(static_cells, simulation["cells"], strict=True):
            pump_capacity = sum(
                pump["drainage_capacity_mm_hr"] * max(0.0, 1.0 - (
                    ((static["x"] - pump["grid_position"]["x"]) ** 2
                     + (static["y"] - pump["grid_position"]["y"]) ** 2) ** 0.5
                ) / pump["operating_radius_cells"]) ** 2
                for pump in simulation["resources"]["pumps"]
            )
            predicted_depth = max(
                0.0,
                float(dynamic["water_depth_mm"])
                + float(dynamic["rainfall_intensity_mm_hr"]) / 6.0 * (0.2 + 0.8 * float(static["impervious_ratio"]))
                - float(static["infiltration_rate_mm_hr"]) / 6.0
                - (float(static["drainage_capacity_mm_hr"]) + pump_capacity) / 6.0,
            )
            cells.append({**static, **dynamic, "pump_capacity_mm_hr": pump_capacity,
                          "predicted_water_depth_mm": predicted_depth})
        resources = simulation["resources"]
        latest_by_station: dict[str, dict[str, Any]] = {}
        for observation in session.historical_observations:
            previous = latest_by_station.get(observation["station_id"])
            if previous is None or observation["timestamp"] > previous["timestamp"]:
                latest_by_station[observation["station_id"]] = observation
        weather = []
        for location in session.locations:
            if location["kind"] != "weather_station":
                continue
            record = latest_by_station.get(location["id"], {})
            weather.append({
                "station_id": location["id"],
                "name": location["name"],
                "rainfall_mm_hr": float(record.get("rainfall_mm_hr", 0.0)),
                "wind_kmh": float(record.get("wind_speed_kmh", 0.0)),
                "air_pressure_hpa": float(record.get("pressure_hpa", 1013.0)),
                "humidity_pct": float(record.get("humidity_pct", 0.0)),
                "temperature_c": float(record.get("temperature_c", 0.0)),
            })
        result: dict[str, Any] = {
            **{key: value for key, value in session.map_document.items() if key != "cells"},
            **simulation,
            "session_id": session.session_id,
            "cells": cells,
            "weather_observations": weather,
            "budget_credits": resources["budget_remaining_credits"],
            "available_resources": [
                {"id": "pump", "name": "Drainage pump", "count": resources["inventory"]["pumps"], "cost": 40},
                {"id": "barrier", "name": "Flood barrier", "count": resources["inventory"]["barriers"], "cost": 25},
                {"id": "rescue-boat", "name": "Rescue boat", "count": resources["inventory"]["rescue_boats"], "cost": 35},
            ],
            "simulation": {
                key: simulation[key]
                for key in (
                    "timestep_minutes", "dt_hours", "elapsed_minutes", "elapsed_seconds",
                    "maximum_water_depth_mm", "average_water_depth_mm", "flooded_road_count",
                    "hospital_access_status", "water_volume_balance", "resources",
                    "location_accessibility", "total_flooded_cells", "flooded_road_count",
                )
            },
            "historical_observation_count": len(session.historical_observations),
            "scenario_progress": {
                "started": session.scenario_started,
                "active": session.scenario_active,
                "complete": session.scenario_complete,
                "step": session.scenario_step,
                "total_steps": len(session.scenario_rainfall_mm_hr),
                "next_rainfall_mm_hr": (
                    session.scenario_rainfall_mm_hr[session.scenario_step]
                    if session.scenario_step < len(session.scenario_rainfall_mm_hr) else None
                ),
            },
            "prediction_model_results": session.prediction_model_results,
            "mission_state": {
                "mission_id": "protect-eastbank",
                "title": "Protect Eastbank",
                "objectives": dict(session.objective_progress),
                "completed_count": sum(session.objective_progress.values()),
                "total_count": len(session.objective_progress),
            },
            "response_outcome": GameSessionManager._response_outcome(session, simulation),
        }
        if include_history:
            result["historical_observations"] = list(session.historical_observations)
        return result

    @staticmethod
    def _response_outcome(session: GameSession, simulation: dict[str, Any]) -> dict[str, Any]:
        cells = simulation["cells"]
        flooded = [cell for cell in cells if cell["water_depth_mm"] >= 1.0]
        roads = [cell for cell in cells if cell["is_road"]]
        residential = [place for place in session.locations if place["kind"] == "residential"]
        homes = []
        for place in residential:
            owned = [cell for cell in cells if cell["building_id"] == place["id"]]
            depth = max((cell["water_depth_mm"] for cell in owned), default=0.0)
            homes.append({"id": place["id"], "name": place["name"], "x": place["x"], "y": place["y"],
                "residents": 25, "maximum_water_depth_mm": depth, "at_risk": depth >= 25.0})
        at_risk = [home for home in homes if home["at_risk"]]
        evacuated_ids: set[str] = set()
        evacuated = 0
        for boat in session.engine.get_state()["resources"]["rescue_boats"]:
            bx, by = boat["grid_position"]["x"], boat["grid_position"]["y"]
            radius = boat["operating_radius_cells"]
            capacity = boat["evacuation_capacity"]
            width = session.map_document["columns"]
            indexed = {(cell["x"], cell["y"]): cell for cell in cells}
            reachable = {(bx, by)}
            frontier = [(bx, by, 0)]
            while frontier:
                cx, cy, steps = frontier.pop(0)
                if steps >= radius:
                    continue
                for nx, ny in ((cx, cy - 1), (cx + 1, cy), (cx, cy + 1), (cx - 1, cy)):
                    if (nx, ny) in reachable or not (0 <= nx < width and 0 <= ny < session.map_document["rows"]):
                        continue
                    neighbor_cell = indexed[(nx, ny)]
                    passable = not neighbor_cell["building_id"] and (
                        neighbor_cell["is_road"] or neighbor_cell["terrain_type"] in {"river", "canal"}
                        or neighbor_cell["water_depth_mm"] >= 25.0
                    )
                    if passable:
                        reachable.add((nx, ny))
                        frontier.append((nx, ny, steps + 1))
            for home in at_risk:
                distance = ((home["x"] - bx) ** 2 + (home["y"] - by) ** 2) ** 0.5
                home_cells = [(cell["x"], cell["y"]) for cell in cells if cell["building_id"] == home["id"]]
                access_points = {(x, y) for hx, hy in home_cells for x, y in
                                 ((hx, hy - 1), (hx + 1, hy), (hx, hy + 1), (hx - 1, hy))}
                accessible = distance <= radius and bool(reachable & access_points)
                if home["id"] not in evacuated_ids and accessible and capacity >= home["residents"]:
                    evacuated += home["residents"]
                    capacity -= home["residents"]
                    evacuated_ids.add(home["id"])
        resources = simulation["resources"]
        access = simulation["location_accessibility"]
        evaluation = session.prediction_model_results.get("evaluation", {})
        metrics = [evaluation.get(key, {}).get("metrics", {}).get("mae") for key in ("moving_average", "linear_regression")]
        valid_metrics = [value for value in metrics if isinstance(value, (int, float))]
        forecast_quality = round(200.0 * max(0.0, 1.0 - (min(valid_metrics) / 40.0)), 1) if valid_metrics else 0.0
        road_score = 150.0 * (1.0 - simulation["flooded_road_count"] / max(1, len(roads)))
        residential_score = 150.0 * (1.0 - len(at_risk) / max(1, len(homes)))
        identified = session.identified_risk_cells
        risk_cells = [cell for cell in cells if cell["flood_risk_index"] >= 50.0 or cell["water_depth_mm"] >= 25.0]
        true_positive = sum((cell["x"], cell["y"]) in identified for cell in risk_cells)
        precision = true_positive / max(1, len(identified))
        recall = true_positive / max(1, len(risk_cells))
        risk_score = 150.0 * (2 * precision * recall / max(0.001, precision + recall)) if identified and risk_cells else 0.0
        budget_fraction = resources["budget_remaining_credits"] / max(1, resources["budget_initial_credits"])
        rain_volume = simulation["water_volume_balance"]["cumulative_rainfall_m3"]
        pump_usefulness = min(1.0, simulation["water_volume_balance"]["pump_removal_m3"] / max(1.0, rain_volume))
        evacuation_effectiveness = evacuated / max(1, sum(home["residents"] for home in at_risk))
        efficiency_score = 75.0 * budget_fraction + 37.5 * pump_usefulness + 37.5 * evacuation_effectiveness
        for home in homes:
            home["evacuated"] = home["id"] in evacuated_ids
        score_parts = {
            "forecast_quality": forecast_quality,
            "risk_identification": round(risk_score, 1),
            "hospital_protection": 200.0 if access.get("eastbank-hospital") == "accessible" else 0.0,
            "road_accessibility": round(max(0.0, road_score), 1),
            "residential_protection": round(max(0.0, residential_score), 1),
            "resource_efficiency": round(min(150.0, efficiency_score), 1),
        }
        score = round(sum(score_parts.values()))
        ending = ("The Prepared City" if score >= 750 else "The Narrow Escape" if score >= 450 else "The Flooded City") if session.scenario_complete else None
        return {
            "total_flooded_cells": len(flooded),
            "flooded_road_count": simulation["flooded_road_count"],
            "hospital_access": access.get("eastbank-hospital", "unknown"),
            "school_access": access.get("eastbank-school", "unknown"),
            "residential_locations": homes,
            "residential_locations_at_risk": len(at_risk),
            "risk_cells_identified": len(identified),
            "risk_cells_actual": len(risk_cells),
            "residents_evacuated": evacuated,
            "remaining_water_depth_mm": simulation["maximum_water_depth_mm"],
            "pump_water_removed_m3": simulation["water_volume_balance"]["pump_removal_m3"],
            "remaining_budget_credits": resources["budget_remaining_credits"],
            "score": score,
            "score_breakdown": score_parts,
            "ending": ending,
            "finalized": session.scenario_complete,
        }

    def get_state(self, session_id: str) -> dict[str, Any]:
        session = self._require(session_id)
        with session.lock:
            return self._state(session)

    def set_rainfall(self, session_id: str, intensity_mm_hr: float) -> dict[str, Any]:
        session = self._require(session_id)
        with session.lock:
            session.engine.set_rainfall(intensity_mm_hr)
            session.scenario_active = False
            session.scenario_complete = False
            session.objective_progress["review_weather"] = True
            return self._state(session)

    def advance(self, session_id: str, steps: int) -> dict[str, Any]:
        session = self._require(session_id)
        with session.lock:
            if session.scenario_complete:
                return self._state(session)
            if session.scenario_active:
                for _ in range(steps):
                    if session.scenario_step >= len(session.scenario_rainfall_mm_hr):
                        session.scenario_active = False
                        session.scenario_complete = True
                        break
                    rainfall = session.scenario_rainfall_mm_hr[session.scenario_step]
                    session.engine.set_rainfall(rainfall)
                    session.engine.advance(1)
                    session.scenario_step += 1
                if session.scenario_step >= len(session.scenario_rainfall_mm_hr):
                    session.scenario_active = False
                    session.scenario_complete = True
            else:
                session.engine.advance(steps)
            session.objective_progress["advance_simulation"] = True
            return self._state(session)

    def start_flood_scenario(self, session_id: str) -> dict[str, Any]:
        session = self._require(session_id)
        with session.lock:
            # Start the final storm from dry ground while retaining equipment deployed in response planning.
            placed = session.engine.get_state()["resources"]
            session.engine.reset(session.seed)
            for pump in placed["pumps"]:
                p = pump["grid_position"]
                session.engine.place_pump((p["x"], p["y"]), pump["drainage_capacity_mm_hr"],
                                          pump["operating_radius_cells"], pump["deployment_cost"])
            for barrier in placed["barriers"]:
                p = barrier["position"]
                session.engine.place_barrier((p["x"], p["y"]), barrier["direction"],
                                             barrier["height_mm"], barrier["deployment_cost"])
            for boat in placed["rescue_boats"]:
                p = boat["grid_position"]
                session.engine.place_rescue_boat((p["x"], p["y"]), boat["deployment_cost"])
            session.scenario_step = 0
            session.scenario_started = True
            session.scenario_active = bool(session.scenario_rainfall_mm_hr)
            session.scenario_complete = False
            if session.scenario_active:
                session.engine.set_rainfall(session.scenario_rainfall_mm_hr[0])
            return self._state(session)

    def place_resource(self, session_id: str, resource: dict[str, Any]) -> dict[str, Any]:
        session = self._require(session_id)
        with session.lock:
            position = (int(resource["x"]), int(resource["y"]))
            resource_type = resource["resource_type"]
            if resource_type == "pump":
                session.engine.place_pump(
                    position,
                    40.0,
                    2.5,
                    40,
                )
            elif resource_type == "barrier":
                direction = resource.get("direction")
                if direction not in {"N", "E", "S", "W"}:
                    raise ValueError("A barrier placement requires direction N, E, S or W")
                session.engine.place_barrier(
                    position,
                    direction,
                    300.0,
                    25,
                )
            elif resource_type == "rescue-boat":
                session.engine.place_rescue_boat(position, 35)
            else:
                raise ValueError("resource_type must be pump, barrier or rescue-boat")
            session.objective_progress["place_resource"] = True
            return self._state(session)

    def reset(self, session_id: str, seed: int | None = None) -> dict[str, Any]:
        session = self._require(session_id)
        with session.lock:
            chosen_seed = session.seed if seed is None else seed
            session.engine.reset(chosen_seed)
            session.seed = chosen_seed
            weather = generate_weather_data(chosen_seed)
            session.historical_observations = tuple(record.to_dict() for record in weather.historical)
            scenario_by_time: dict[str, list[float]] = {}
            for observation in weather.eastbank_scenario:
                scenario_by_time.setdefault(observation.timestamp, []).append(observation.rainfall_mm_hr)
            session.scenario_rainfall_mm_hr = tuple(
                sum(values) / len(values) for _, values in sorted(scenario_by_time.items())
            )
            session.scenario_step = 0
            session.scenario_active = False
            session.scenario_started = False
            session.scenario_complete = False
            session.objective_progress = {objective: False for objective in session.objective_progress}
            session.identified_risk_cells.clear()
            session.prediction_model_results.clear()
            return self._state(session)

    def report_objective(self, session_id: str, objective_id: str) -> dict[str, Any]:
        session = self._require(session_id)
        with session.lock:
            if objective_id not in session.objective_progress:
                raise ValueError(f"Unknown mission objective '{objective_id}'")
            session.objective_progress[objective_id] = True
            return self._state(session)

    def identify_risk(self, session_id: str, x: int, y: int) -> dict[str, Any]:
        session = self._require(session_id)
        with session.lock:
            width, height = session.map_document["columns"], session.map_document["rows"]
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError("Risk marker is outside the Eastbank grid")
            session.identified_risk_cells.add((x, y))
            session.objective_progress["review_risk"] = True
            return self._state(session)

    def record_prediction(self, session_id: str, result: dict[str, Any], kind: str = "regression", compared: bool = False) -> None:
        session = self._require(session_id)
        with session.lock:
            session.prediction_model_results[kind] = result
            session.objective_progress["build_forecast"] = True
            if compared:
                session.objective_progress["compare_models"] = True


game_sessions = GameSessionManager()
