# IndustrialPulse AI
Synthetic industrial monitoring, anomaly detection, validation, and simulation MVP.

> This is a deterministic educational/synthetic engineering model, not a safety-certified industrial control system or validated digital twin.

## Features
- Deterministic synthetic master data and 100,000 telemetry records
- Facilities, pumps, tanks, valves, pipes, sensors, operating modes, telemetry, alarms, simulation runs
- Explicit ground-truth scenario records kept separate from detector features
- Rule-based leak, blockage, pump-degradation, sensor-fault detection
- Basic topology and tank-capacity validation
- SQLite persistence for simulation runs and alarms
- FastAPI endpoints and a simple browser dashboard
- Pytest tests and reproducibility checker

## Requirements
Python 3.10+

## Quick start
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
python generate_data.py --telemetry 100000 --seed 20261022
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000 for the dashboard and http://127.0.0.1:8000/docs for the API.

For a fast local smoke test:
```bash
python generate_data.py --telemetry 2000 --seed 20261022
pytest -q
python scripts/reproducibility_check.py --telemetry 1000
```

## Generated files
`data/generated/` contains CSV files and `ground_truth.json`. The ground-truth file is an evaluation artifact and is not passed into the detection functions.

## API
- `GET /api/summary`
- `GET /api/alarms`
- `GET /api/telemetry?limit=100`
- `POST /api/simulations` body: `{"pump_id":"PUMP-001","speed_pct":80}`
- `GET /api/simulations`

## Model assumptions
- Flow is in L/s, pressure in kPa, tank volume in liters.
- The synthetic topology uses a directed graph; each pipe endpoint must exist in the component node registry.
- A simplified pump curve is used: `head = shutoff_head_kpa - curve_k * flow_lps**2`.
- Tank balance uses `volume[t+1] = volume[t] + (inflow - outflow) * dt_seconds`.
- Detection thresholds are configurable constants in `app/engine.py`; they are illustrative and should be calibrated against real plant data before operational use.
- Simulations are simplified scenario comparisons, not hydraulic-network solvers.

## Data dictionary (summary)
| Entity | Primary key | Key relationships | Important units |
|---|---|---|---|
| Facility | facility_id | parent of equipment | — |
| Pump | pump_id | facility_id -> Facility | flow L/s, pressure kPa |
| Tank | tank_id | facility_id -> Facility | capacity/volume L |
| Valve | valve_id | facility_id -> Facility | opening % |
| Pipe | pipe_id | facility_id -> Facility; from/to node IDs | diameter mm, length m |
| Sensor | sensor_id | facility_id -> Facility; component_id | type-specific |
| Telemetry | telemetry_id | sensor_id -> Sensor | flow L/s, pressure kPa, level L |
| OperatingMode | operating_mode_id | facility_id -> Facility | effective timestamps UTC |
| Alarm | alarm_id | optional simulation_run_id | severity enum |
| SimulationRun | simulation_run_id | facility_id -> Facility | seed, config hash |

## Validation and known limitations
- Invalid pipe endpoints are detected by validation; baseline generated topology uses valid endpoints.
- Deliberately invalid tank levels and invalid pipe references are placed in `data/generated/negative_cases.json`, not silently mixed into baseline records.
- Flow residual checks are approximate and depend on sensor coverage and storage changes.
- Rule-based detection is intentionally explainable. Metrics should be computed at scenario/window level, not by treating every telemetry row as an independent anomaly.
- The frontend is intentionally minimal so engineering correctness remains the priority.
