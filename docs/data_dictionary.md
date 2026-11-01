# IndustrialPulse AI — Data Dictionary

## 1. Purpose and Conventions

This document describes the generated CSV data, evaluation artifacts, seed-data exports, and runtime SQLite records used by IndustrialPulse AI.

- **Identifiers:** The generator creates deterministic string identifiers. Their patterns are conventions, not protection against edits to exported files.
- **Timestamps:** Generated timestamps use UTC ISO 8601.
- **CSV types:** Types in this document describe logical values; CSV files do not enforce a schema themselves.
- **Validation:** `validate_dataset()` checks generated files and returns `valid`, `errors`, observed `counts`, and a `checks` object. Errors are strings without severity levels. Missing or unreadable required CSV files raise a file or parser exception instead of returning the normal validation structure.
- **Seed data vs. runtime data:** Seed exports describe the generated dataset. The API's runtime SQLite database is a smaller persistence model and does not store every generated table.

### Runtime database scope

The API runtime database contains `facilities`, `pumps`, `components`, `simulation_runs`, and `alarms`. It does not persist the generated `sensors`, `telemetry`, or `operating_modes` tables. Those tables are included separately in seed SQL exports. Runtime `components` rows preserve component IDs and types, but do not store Pipe endpoint fields or the generated topology.

## 2. Entity and Field Reference

The tables below use these column meanings:

- **Required:** Whether a value must be present in a valid record.
- **Allowed values / units:** Expected format, unit, or controlled values.
- **Validation / relationship:** Uniqueness, constraints, or references to other records.

### 2.1 Facility

**Source:** `facilities.csv`; SQLite runtime table `facilities`

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `facility_id` | string | Yes | `FAC-NNN` | Primary key; deterministic by generator convention, not immutable against external edits. |
| `name` | string | Yes | — | Required display name. |
| `status` | string | Yes | `active`, `inactive` | Facility lifecycle state. |

A Facility has many Pumps, Tanks, Valves, Pipes, Sensors, and OperatingModes. Runtime SimulationRuns reference one Facility. The generated baseline contains three active facilities.

### 2.2 Pump

**Source:** `pumps.csv`; SQLite runtime table `pumps`

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `pump_id` | string | Yes | `PUMP-NNN` | Primary key; deterministic by generator convention, not immutable against external edits. |
| `facility_id` | string | Yes | — | Foreign key to Facility. |
| `nominal_flow_lps` | number | Yes | L/s | Must be greater than zero; used as the detector reference and simulation input. |
| `shutoff_head_kpa` | number | Yes | kPa | Must be greater than zero; simulation input. |
| `curve_k` | number | Yes | Model coefficient | Must be greater than zero; descriptive in the current MVP and not used to solve the network. |
| `status` | string | Yes | `active`, `inactive` | Pump lifecycle state. |

A Facility has many Pumps. In the generated MVP, a Pump may have one associated flow Sensor. The logical model allows a Sensor to monitor one primary component.

### 2.3 Tank

**Source:** `tanks.csv`; seed SQL table `tanks`; runtime identity represented in `components`

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `tank_id` | string | Yes | `TANK-NNN` | Primary key; deterministic by generator convention, not immutable against external edits. |
| `facility_id` | string | Yes | — | Foreign key to Facility. |
| `capacity_liters` | integer | Yes | L | Must be greater than zero. |
| `initial_volume_liters` | integer | Yes | L | Must be between zero and capacity, inclusive. |
| `status` | string | Yes | `active`, `inactive` | Tank lifecycle state. |

A Facility has many Tanks. Level telemetry references a Tank through the Sensor's `component_id`. A valid level reading cannot exceed the Tank's capacity.

### 2.4 Valve

**Source:** `valves.csv`; seed SQL table `valves`; runtime identity represented in `components`

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `valve_id` | string | Yes | `VALVE-NNN` | Primary key; deterministic by generator convention, not immutable against external edits. |
| `facility_id` | string | Yes | — | Foreign key to Facility. |
| `opening_pct` | integer | Yes | 0–100 percent | Inclusive bounds. |
| `state` | string | Yes | `open`, `closed` | Controlled valve state. |
| `status` | string | Yes | `active`, `inactive` | Valve lifecycle state. |

A Facility has many Valves. A Valve is a valid node type for Pipe topology references.

### 2.5 Pipe

**Source:** `pipes.csv`; seed SQL table `pipes`; runtime identity represented in `components`

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `pipe_id` | string | Yes | `PIPE-NNN` | Primary key; deterministic by generator convention, not immutable against external edits. |
| `facility_id` | string | Yes | — | Foreign key to Facility. |
| `from_node_id` | string | Yes | Pump, Tank, or Valve ID | Must identify an existing topology node in the same Facility. |
| `to_node_id` | string | Yes | Pump, Tank, or Valve ID | Must identify a different existing node in the same Facility. |
| `diameter_mm` | integer | Yes | mm | Must be greater than zero. |
| `length_m` | number | Yes | m | Must be greater than zero. |
| `status` | string | Yes | `active`, `inactive` | Pipe lifecycle state. |

A Facility has many Pipes. Each Pipe contains two directed endpoint references. The current generator creates a chain of references; it does not calculate hydraulic behaviour.

### 2.6 Sensor

**Source:** `sensors.csv`; included in seed SQL exports

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `sensor_id` | string | Yes | `SNS-NNN` | Primary key; deterministic by generator convention, not immutable against external edits. |
| `facility_id` | string | Yes | — | Foreign key to Facility; must match the monitored component's Facility. |
| `component_id` | string | Yes | Pump, Tank, or Facility ID | Identifies the monitored target, not a separate instrument record. |
| `sensor_type` | string | Yes | `flow`, `pressure`, `level` | Determines the measurement unit and valid role. |
| `unit` | string | Yes | `L/s`, `kPa`, `L` | Must match `sensor_type`. |
| `measurement_role` | string | Yes | `inlet`, `outlet`, `level`, `pressure` | Flow sensors use inlet/outlet; level and pressure sensors use their matching role. |
| `status` | string | Yes | `active`, `inactive` | Sensor lifecycle state. |

A Facility has many Sensors. Each Sensor monitors one primary component and can have many Telemetry records. The MVP has no separate component-to-sensor bridge table.

### 2.7 Telemetry

**Source:** `telemetry.csv`; included in seed SQL exports

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `telemetry_id` | string | Yes | `TEL-NNNNNN` | Primary key; deterministic by generator convention, not immutable against external edits. |
| `sensor_id` | string | Yes | — | Foreign key to Sensor. |
| `timestamp` | timestamp | Yes | UTC ISO 8601 | Must parse; `(sensor_id, timestamp)` must be unique. |
| `facility_id` | string | Yes | — | Must match Sensor metadata. |
| `component_id` | string | Yes | — | Must match the Sensor's monitored target. |
| `sensor_type` | string | Yes | `flow`, `pressure`, `level` | Must match Sensor metadata. |
| `unit` | string | Yes | `L/s`, `kPa`, `L` | Must match Sensor metadata. |
| `measurement_role` | string | Yes | `inlet`, `outlet`, `level`, `pressure` | Must match Sensor metadata. |
| `value` | number | Yes | Sensor unit | Must be finite and non-negative; Tank level cannot exceed capacity. |
| `quality_status` | string | Yes | `good`, `suspect` | `suspect` readings are excluded from process rules. |

One Sensor has many Telemetry records. Ground-truth labels are not fields in Telemetry and are not detector inputs. The synthetic sensor-fault injection marks affected rows as `suspect`. The detector receives this quality metadata to exclude those rows from process rules while its stuck-value rule can still generate a sensor-fault alarm.

### 2.8 OperatingMode

**Source:** `operating_modes.csv`; included in seed SQL exports

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `operating_mode_id` | string | Yes | `MODE-NNN` | Primary key; deterministic by generator convention, not immutable against external edits. |
| `facility_id` | string | Yes | — | Foreign key to Facility. |
| `mode_name` | string | Yes | Free text; generated value is `normal` | Required. |
| `effective_from` | timestamp | Yes | UTC ISO 8601 | Must parse as a timestamp. |
| `effective_to` | timestamp | No | UTC ISO 8601 or blank | If present, cannot precede `effective_from`. |
| `status` | string | Yes | `active`, `inactive` | Active date ranges for the same Facility must not overlap. |

A Facility has many OperatingModes. The generated baseline has one open-ended active mode per Facility.

### 2.9 Alarm

**Source:** SQLite runtime table `alarms`

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `alarm_id` | string | Yes | `ALM-NNNNNN` | Primary key; detector sequence identifier. |
| `simulation_run_id` | string | No | — | Optional foreign key to SimulationRun; API-generated detector alarms are not tied to a simulation run. |
| `component_id` | string | Yes | Facility or equipment ID | Foreign key to a known component. |
| `alarm_type` | string | Yes | Detector rule category | Required. |
| `severity` | string | Yes | `low`, `medium`, `high`, `critical` | Restricted by a database constraint. |
| `rule_id` | string | Yes | Detector rule ID | Required. |
| `observed_value` | number | No | Depends on rule | Optional. |
| `expected_value` | JSON text | No | Depends on rule | Optional detector reference. |
| `explanation` | string | Yes | — | Required explanation. |
| `created_at` | timestamp | Yes | UTC ISO 8601 | Persistence timestamp. |

Alarm lifecycle transitions are not implemented. Detector records contain sensor IDs and time windows in memory, but the SQLite `alarms` table does not persist those fields.

### 2.10 SimulationRun

**Source:** SQLite runtime table `simulation_runs`

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `simulation_run_id` | string | Yes | `SIM-` plus UUID hex | Primary key; a new identifier is created for each execution. |
| `facility_id` | string | Yes | — | Foreign key to Facility. |
| `pump_id` | string | Yes | — | Foreign key to Pump. |
| `config_json` | JSON object | Yes | Run ID, pump, speed, seed, model version, assumptions | Application and fresh-database checks require identity and input fields. |
| `configuration_hash` | string | Yes | SHA-256 hex | Hash of canonical serialized configuration; 64 characters. |
| `seed` | integer | Yes | Non-negative | Must match the configuration. |
| `status` | string | Yes | `completed`, `failed` | Database constraint; status-transition workflow is not implemented. |
| `created_at` | timestamp | Yes | UTC ISO 8601 | Required. |
| `output_json` | JSON object | Yes | Predicted flow/head and assumptions note | Must be a JSON object containing predicted values. |

A Facility and a Pump can each have many SimulationRuns. A SimulationRun may have associated Alarms; `simulation_run_id` on Alarm is optional.

## 3. Generated JSON and Supporting Artifacts

### `seed_data.json`

Created on demand by `scripts/export_data.py --seed-json`. It contains record arrays for all eight CSV seed tables. It is separate from scenario labels and simulation-result exports. The modeled `flow_balances.csv` is not included in the JSON/SQL seed export.

### `ground_truth.json`

Contains scenario labels and exclusive row-index windows used for evaluation after detection. A ground-truth `component_id` identifies the scenario target and may refer to a Pump, Sensor, Facility, or Pipe, depending on the scenario.

Each ground-truth record contains:

- `scenario_id`
- `issue_type`
- `component_id`
- `start_index`
- `end_index`
- `expected_decision`
- `ground_truth`
- `label_source`

The window uses half-open indexing: `[start_index, end_index)`. The evaluator loads this file after running detection; the labels are not detector features.

### `validation_summary.json`

Produced by dataset validation. It records observed record counts, errors, tolerance, and details for each checked flow-balance interval. For the full baseline, it reports 100,000 telemetry rows and nine valid modeled balance intervals.

### `source_manifest.json`

Records the seed, telemetry count, generator name, synthetic-data provenance, and SHA-256 checksums for generated entity CSVs, `flow_balances.csv`, `ground_truth.json`, and `validation_summary.json`. It does not checksum itself or record Python/package versions.

### `tests/fixtures/negative_cases.json`

Stores invalid test inputs used to verify rejection behaviour. These cases are test fixtures and are not inserted into the valid baseline dataset.

## 4. Flow-Balance Validation Artifact

**Source:** `flow_balances.csv`

This artifact is separate from sensor Telemetry and ground-truth labels. The generated baseline contains nine modeled steady-state intervals: three demand factors for each of three Facilities.

| Field | Type | Required | Allowed values / unit | Validation and relationship |
|---|---|---:|---|---|
| `balance_id` | string | Yes | `BAL-<facility>-NN` | Unique interval identifier. |
| `facility_id` | string | Yes | — | Foreign key to Facility. |
| `interval_start` | timestamp | Yes | UTC ISO 8601 | Start of the modeled or measured interval. |
| `interval_seconds` | number | Yes | seconds | Must be finite and greater than zero. |
| `measurement_basis` | string | Yes | `modeled`, `measured` | Explicitly distinguishes model output from observations. |
| `model_name` | string | For modeled rows | `steady_state_bottlenecked_nominal_capacity` | Identifies the implemented modeled-flow rule. |
| `demand_factor` | number | For modeled rows | `(0, 1]` | Multiplier applied to bottleneck capacity. |
| `source_pump_capacities_json` | JSON object | For modeled rows | Pump IDs and nominal L/s capacities grouped by inlet/outlet role | Pump references, roles, and capacities are checked against Pump and Sensor source records. |
| `inlet_flows_lps` | JSON array | Yes | Non-negative L/s | Flow source terms for the interval. |
| `outlet_flows_lps` | JSON array | Yes | Non-negative L/s | Flow sink terms for the interval. |
| `tank_volume_change_liters` | number | Yes | L over the interval | Positive values indicate increased storage; negative values indicate decreased storage. |

For each interval, the validator derives the residual:

```text
residual_lps =
    sum(inlet_flows_lps)
    - sum(outlet_flows_lps)
    - tank_volume_change_liters / interval_seconds
```

The allowed absolute residual is **8 L/s**. Values must be finite, flow arrays must be non-empty and non-negative, and interval duration must be positive. The baseline has nine valid modeled intervals; these are not measured telemetry and do not establish conservation in a real network.

Modeled intervals must also use the supported model name, have a demand factor in `(0, 1]`, include complete pump references by flow role, match nominal capacities in Pump master data, match the modeled flow calculation, and use zero modeled tank-volume change. Measured rows are checked for balance inputs and residual, but do not undergo the modeled-source cross-check.

The flow-balance artifact is not included in the JSON/SQL seed export. It remains available as a baseline CSV and is hashed by `source_manifest.json`.

## 5. Relationship and Validation Summary

| Relationship / rule | Expected behaviour |
|---|---|
| Facility → Pumps, Tanks, Valves, Pipes, Sensors, OperatingModes | Child records reference an existing Facility. |
| Sensor → Telemetry | Telemetry sensor ID and duplicated metadata must agree with the Sensor record. |
| Pipe → endpoints | Both endpoints must exist in the same Facility and must be different nodes. |
| Tank → level telemetry | Level readings must remain between zero and Tank capacity. |
| Telemetry uniqueness | A `(sensor_id, timestamp)` pair cannot occur more than once. |
| OperatingMode ranges | Timestamps must parse; an end time cannot precede a start time; active ranges for one Facility cannot overlap. |
| Modeled flow balance | Source capacities and modeled flows must agree with the documented rule; absolute residual must be no more than 8 L/s. |
| Simulation traceability | Run identity, pump/facility references, seed, configuration hash, and output must be internally consistent. |
| Ground-truth separation | Scenario labels are used by evaluation after detection and are not detector input. |

## 6. Interpretation Notes and Limitations

- CSV files do not enforce the logical types or relationships described here; validation code performs those checks.
- Identifier patterns are generator conventions and should not be treated as immutable external identifiers.
- The runtime SQLite model is not a full copy of the generated master-data model. In particular, runtime `components` do not preserve Pipe endpoint topology.
- The sensor-fault scenario includes `suspect` quality metadata. That metadata is available to the detector; the ground-truth labels remain separate.
- Flow-balance records are modeled steady-state values based on nominal capacities and assumptions, not synchronized boundary measurements or a hydraulic solution.
- The project is a local synthetic-data prototype. Its schema and checks demonstrate traceability and validation workflows, not production-grade industrial data governance or safety assurance.
