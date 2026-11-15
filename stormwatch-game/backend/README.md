# STORMWATCH Backend

FastAPI provides the game session API, synthetic weather observations, data science calculations, and flood simulation. The flood and analytics calculations run in Python and supply the results used by the game.

## Requirements

- Python 3.11 or newer
- Dependencies from `requirements.txt`

## Local development

From the repository root, create and install the backend environment using `scripts/setup.ps1`, then start the API:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000
```

Or, from this directory, activate the virtual environment and run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: <http://127.0.0.1:8000/api/health>. Interactive API documentation: <http://127.0.0.1:8000/docs>.

The backend has no required `.env` file, credentials, or external data dependency. Weather and city data are synthetic and reproducible. The shared map definition lives in `../shared/eastbank_grid.json`.

## Main API groups

- `/api/game/*` — create and advance game sessions, place resources, and retrieve state
- `/api/analytics/*` — statistics, moving averages, regression, correlation, and evaluation
- `/api/scenario` and `/api/map/eastbank` — scenario and map definitions
- `/api/simulation/*` — flood simulation operations

See the generated OpenAPI page at `/docs` for request and response schemas.
