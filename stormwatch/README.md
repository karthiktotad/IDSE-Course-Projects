# STORMWATCH: Eastbank Flood Response

**Learn data science by trying to keep a coastal hospital connected during a flood.**

> **[OPEN THE PLAYER GUIDE, LEARNING OUTCOMES & PLAYTEST EVIDENCE](HOW_TO_PLAY.md)**
> Step-by-step gameplay instructions, task concepts, screenshots, and peer feedback.

STORMWATCH is an interactive flood-response game. As Eastbank's Chief Engineer, the player explores rainfall data, tests a regression model, deploys limited response resources, and makes forecasts while a simulated 24-hour storm unfolds. Maya Reyes, the field lead, introduces each task and offers on-demand guidance. Player choices affect the simulated city and its final mission score.

The game uses synthetic, reproducible weather and flood data for learning; it is not an operational forecast or emergency tool.

**[Play STORMWATCH online](https://stormwatch-eastbank-107l.onrender.com/)**

## Run locally (Windows)

Requirements: Windows 10/11, PowerShell, Python 3.11+, and Node.js 20+.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\run.ps1
```

After startup, open the local frontend address printed by Vite. It proxies API requests to the FastAPI backend. Press `Ctrl+C` in the launcher terminal to stop the services.

The backend requires no environment file. To change the frontend's API proxy, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_PROXY_TARGET`. Local `.env` files are ignored by Git.

## Build and deploy

Build the frontend with `npm run build` from `frontend/`. Backend checks can be run from the repository root with `backend/.venv/Scripts/python.exe -m pytest -q`.

To run the combined production container, use `docker build -t stormwatch .` followed by `docker run --rm -p 10000:10000 stormwatch`. A free Render web service is configured in [`render.yaml`](render.yaml).

## Project structure

- `frontend/` — Vite, TypeScript, and Phaser game interface
- `backend/` — FastAPI game, analytics, and flood simulation
- `shared/eastbank_grid.json` — Eastbank map and simulation grid
- `docs/` — supporting project documentation and gameplay evidence
