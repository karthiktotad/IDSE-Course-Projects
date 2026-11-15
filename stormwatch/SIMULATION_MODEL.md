# Eastbank flood simulation model

This is a deterministic, educational surface-water model. It is useful for comparing player experiments on the Eastbank grid; it is not an operational forecast or a calibrated hydrodynamic model.

## Grid and units

- The engine loads `shared/eastbank_grid.json` through `backend/app/simulation/grid.py`.
- Every simulation cell represents a 32 m × 32 m area (1,024 m²). This physical scale is an explicit game assumption; the map's rendered tile is 32 × 32 pixels.
- Elevation and surface water depth use millimetres. Rainfall, infiltration and drainage capacities use millimetres per hour. Each timestep is 10 minutes (`dt_hours = 1/6`). Water volumes in the balance are cubic metres.
- The map's building cells are obstacles to lateral transfer. Rain falling on a roof is routed to adjacent flowable cells; a fully enclosed roof retains its local surface water.

## Rain and losses

The runoff coefficient is `0.20 + 0.75 × impervious_ratio`, clipped to `[0, 1]`. For each cell the engine first computes `rainfall_intensity × dt_hours × runoff_fraction`. It then applies the cell's infiltration capacity to the remaining rainfall, scaled by its pervious fraction. Rain that exceeds infiltration capacity joins surface runoff. This partitions all precipitation between infiltration and surface input, so the water balance closes.

Natural drainage is capped at 2 mm/hour per ordinary flow cell. Mapped drain inlets contribute their authored capacity as installed drainage. River and canal conveyance is handled by lateral flow instead of being treated as a sink. Pumps add a configurable capacity field with a squared linear distance attenuation; all drainage is clamped to the water actually present.

## Lateral flow, rivers and barriers

The engine compares absolute water-surface elevations (`terrain elevation + water depth`) across the four orthogonal edges. A lower neighbour receives a potential transfer proportional to the surface difference. Buildings are excluded as sources and destinations. The engine computes all edge transfers from the same timestep snapshot, caps total outgoing water per source by `max_transfer_fraction` (default 0.25), accumulates equal-and-opposite values in a separate buffer, then applies that buffer once.

Barriers belong to one adjacent-cell edge. Their crest is the higher adjacent terrain elevation plus barrier height. An edge blocks flow while the source surface is at or below that crest, and permits overtopping above it. River cells use the same edge-flow calculation and can overflow to a lower bank. River cells on the west map boundary can discharge toward a fixed 0 mm sea level; that boundary outflow is included in the balance.

## Simplifications

- The model has no momentum, inertia, sub-cell channel geometry, culvert routing, soil saturation memory, evaporation, tide schedule or time-varying storm forecast.
- Infiltration is computed from the current timestep's remaining rainfall; standing water does not infiltrate later.
- Edge flow is a stable heuristic, not the shallow-water equations. The fixed sea-level boundary is a convenient outlet condition.
- Rescue boats are tracked as response resources but do not change water movement.
- The seed is stored with the run and is used by seeded scenario inputs; with a fixed rainfall grid and resource actions, the flood update itself is deterministic.

## Local simulation API

The FastAPI app exposes `GET /api/simulation/state` and `POST` routes for `/api/simulation/initialize`, `/api/simulation/rainfall`, `/api/simulation/advance`, `/api/simulation/barriers`, `/api/simulation/pumps`, `/api/simulation/rescue-boats`, and `/api/simulation/reset`. The legacy `/api/map/eastbank` response now joins static Eastbank metadata with the live engine state; it does not contain a predesigned water image.
