# Data dictionary
All IDs are immutable strings with deterministic prefixes and zero-padded counters. Timestamps are UTC ISO-8601.

## Core tables
- `facilities.csv`: `facility_id` (string, required, unique, `FAC-NNN`), `name` (string, required), `status` (enum: active/inactive).
- `pumps.csv`: `pump_id` (PK), `facility_id` (FK), `nominal_flow_lps` (float > 0, L/s), `shutoff_head_kpa` (float > 0, kPa), `curve_k` (float > 0), `status` (enum).
- `tanks.csv`: `tank_id` (PK), `facility_id` (FK), `capacity_liters` (integer > 0, L), `initial_volume_liters` (integer, 0 <= volume <= capacity), `status` (enum).
- `valves.csv`: `valve_id` (PK), `facility_id` (FK), `opening_pct` (integer 0..100, %), `state` (enum: open/closed), `status` (enum).
- `pipes.csv`: `pipe_id` (PK), `facility_id` (FK), `from_node_id`/`to_node_id` (required valid component-node IDs), `diameter_mm` (positive integer, mm), `length_m` (positive float, m), `status` (enum).
- `sensors.csv`: `sensor_id` (PK), `facility_id` (FK), `component_id` (required component/facility ID), `sensor_type` (enum: flow/pressure/level), `unit` (L/s, kPa, L), `measurement_role` (enum by use: inlet/outlet/level/pressure), `status` (enum).
- `telemetry.csv`: `telemetry_id` (PK), `sensor_id` (FK), `timestamp` (UTC), `facility_id`, `component_id`, `sensor_type`, `unit`, `measurement_role`, `value` (numeric), `quality_status` (good/suspect).
- `operating_modes.csv`: `operating_mode_id` (PK), `facility_id` (FK), `mode_name`, `effective_from`, optional `effective_to`, `status`.
- `ground_truth.json`: evaluation labels for deterministic injected scenarios; never a detector feature.
- `negative_cases.json`: deliberate invalid fixtures kept separate from baseline records.
- Runtime `simulation_runs`: run ID, facility FK (logical), configuration JSON/hash, seed, status, timestamps, output JSON.
- Runtime `alarms`: alarm ID, optional simulation run ID, component ID, alarm type, severity, rule ID, observed/expected values, explanation, timestamp.

## Identifier semantics
`sensor_id` identifies the measuring instrument. `component_id` identifies the asset or facility that instrument monitors. For example, sensor `SNS-001` monitors component `PUMP-001`; a sensor-fault alarm therefore carries `sensor_id: SNS-001` and `component_id: PUMP-001`.

In `ground_truth.json`, the legacy field named `component_id` is the scenario's target ID, not necessarily a component ID. The issue type determines its namespace: pump IDs for pump degradation, sensor IDs for sensor faults, facility IDs for the leak proxy, and pipe IDs for blockage scenarios. Scenario `start_index` is inclusive and `end_index` is exclusive in the generated telemetry row order.

The detector's in-memory alarm records include `sensor_id` (or `sensor_ids` for facility proxies) and an observed timestamp window. The current SQLite alarm table does not persist those additional fields.

## Cardinality
Facility 1:N equipment and operating modes. Sensor 1:N telemetry. SimulationRun 1:N alarms (optional alarm association for alarms raised outside a simulation). A component may have N sensors; if sensors monitor multiple components, a bridge table is needed. Current MVP models one primary component per sensor.
