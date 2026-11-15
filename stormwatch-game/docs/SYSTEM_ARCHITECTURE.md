# System Architecture

## Runtime components

```text
Browser: Vite + TypeScript + Phaser 3.90 + Chart.js
          typed frontend/src/api.ts client
                    │ /api proxy (local HTTP)
                    ▼
Python 3.11+ : FastAPI (backend/app/main.py)
       ├── game_sessions.py: in-memory sessions, mission and response outcome
       ├── simulation/: NumPy grid, rainfall, drainage, water flow and resources
       ├── analytics/: seeded weather, statistics, smoothing, regression, correlation and evaluation
       └── shared/eastbank_grid.json: static authored source shared by renderer and simulation
```

Python owns game session state, flood physics, analytics, and scoring. The frontend sends user actions through typed API functions and renders the returned snapshots. Water-depth interpolation is a visual transition only; it is not simulation state. Vite forwards `/api` to `http://127.0.0.1:8000`.

## State and persistence

`POST /api/game/new` creates a seeded in-memory session. The session contains the Eastbank grid, historical observations, scenario rainfall, current flood engine state, resources, budget, forecasts, risks and mission state. Backend restart removes sessions. Frontend campaign stage/objective persistence uses local storage. There is no database, cloud dependency, authentication or external API at runtime.

## API groups

| Route | Purpose |
|---|---|
| `GET /api/health` | Health check |
| `POST /api/game/new` | Create seeded Eastbank session |
| `GET /api/game/{id}/state` | Retrieve session/map/simulation snapshot |
| `POST /api/game/{id}/rainfall` | Set rainfall intensity |
| `POST /api/game/{id}/advance` | Advance 1–6 steps per request |
| `POST /api/game/{id}/scenario/start` | Begin the final scenario |
| `POST /api/game/{id}/place-resource` | Validate and deploy pump, edge barrier or boat |
| `POST /api/game/{id}/mission/objective` | Record mission objective |
| `POST /api/game/{id}/identify-risk` | Mark a grid cell for score evaluation |
| `POST /api/game/{id}/reset` | Reset the session |
| `POST /api/analytics/{statistics,moving-average,regression,correlation,evaluate}` | Perform analysis operations |
| `POST /api/analytics/forecast` | Generate future model estimates |
| `GET /api/analytics/{weather,lab}` | Retrieve seeded weather and analysis lab data |
| `GET /api/map/eastbank` | Retrieve map and simulation display data |

FastAPI validation errors use 422 responses, unknown sessions use 404, and unexpected startup/map errors are reported rather than hidden. Game session updates are protected by per-session locks.

## Coordinates and map ownership

Cell `(x, y)` uses x increasing eastward and y increasing southward. Bounds are `0≤x<32`, `0≤y<24`. Phaser places cell origin at `(x×32, y×32)` pixels. The simulation loads the same `shared/eastbank_grid.json`; static objects have stable IDs and map coordinates. This keeps art, inspection and simulation aligned.

## Local development

Windows setup is in `scripts/setup.ps1`; `scripts/run.ps1` starts and checks both local processes. Logs go to `%TEMP%\stormwatch-logs`. The game and API use loopback URLs and bundled local assets. First-time package installation needs Python package and npm registries; after dependencies are installed, runtime needs no cloud service or external API.
