# STORMWATCH: The Last 24 Hours — Game Design

## Premise

Novara's Eastbank district is approaching a severe rainfall event. The player is the Flood Intelligence Engineer. They inspect local observations, test forecasting approaches, then allocate limited emergency resources to keep the hospital, school, homes and connecting roads operating.

## Player loop

1. Read the city through its map, weather stations and infrastructure.
2. Investigate six-hour rainfall samples and summarize their variation.
3. Smooth noisy observations with an adjustable moving-average window.
4. Fit and inspect a rainfall-to-water-depth line, then test it against held-out observations.
5. Mark vulnerable map cells and prepare a pump, barrier and rescue boat.
6. Run the 24-hour storm in ten-minute simulation increments and review the city report.

## Eastbank map

The authored grid is 32 columns by 24 rows, with 32-pixel orthogonal cells (1024×768 logical pixels). `shared/eastbank_grid.json` stores the static map, terrain, elevation, hydrologic properties, buildings, stable location IDs and interactive objects. The Westbank river edge and a connected drainage canal organize the district's geography. The hospital and its approach road occupy low terrain; the school, control centre, residences, four weather stations and drainage inlets are connected by roads. The game renders a locally bundled CC0 Kenney Tiny City atlas with procedural map details. Camera movement is bounded to the map.

## Interface and interaction

The city remains the main play surface. Drag pans the map; wheel and zoom controls change scale. Click or hover cells to inspect coordinates, terrain and live values. Map layer buttons expose elevation, rain, water, drainage and risk data. The mission, detail and emergency response panels provide compact support for the map. The prediction lab uses interactive Chart.js plots; response tools preview candidate placements and validate them with the Python session before charging the budget.

## Campaign stages

The five stages are The First Drop, The Hidden Flood Pattern, Predict the Flood, The Prediction Failure and Save Novara. Objectives gate new stages, completed stages can be replayed, and campaign progress is stored in browser local storage. Each live simulation session is held in backend memory and is lost on a backend restart.

## Response and endings

The starting budget is 100 credits: pump 40, barrier 25, rescue boat 35. A pump adds attenuated local drainage; a barrier occupies one grid edge and can be overtopped; a boat evacuates reachable at-risk residences subject to route, radius and capacity. The backend computes access, flood exposure, evacuation and a 1000-point score from the actual run. It selects The Prepared City (750+), The Narrow Escape (450–749) or The Flooded City (below 450) after the scenario completes.

## Tone and learning approach

METEO AI offers brief contextual hints. The player sees the data and consequences before reading a short concept explanation. The experience is an educational, deterministic surface-water model, not an operational emergency-management tool.
