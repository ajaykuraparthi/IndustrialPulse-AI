# IndustrialPulse AI

Synthetic industrial monitoring, data validation, rule-based anomaly detection, and reproducible simulation workflows for a local demo environment.

Status: Prototype/demo implementation.

Technology stack: Python, FastAPI, SQLite, Pandas, NumPy, NetworkX, pytest.

Relevant project documentation:
- [docs/architecture.md](docs/architecture.md)
- [docs/data_dictionary.md](docs/data_dictionary.md)
- [docs/simulation_assumptions.md](docs/simulation_assumptions.md)
- [docs/ai_usage/ai_contribution_statement.md](docs/ai_usage/ai_contribution_statement.md)

## Executive Summary

IndustrialPulse AI is a self-contained industrial monitoring MVP built around synthetic facility telemetry and explainable operational rules. The project models a small industrial environment with facilities, pumps, tanks, valves, pipes, and sensors; generates deterministic telemetry; validates structural relationships; applies transparent anomaly checks; and exposes the workflow through a FastAPI API and browser dashboard.

The system is designed for demonstration, evaluation, and reproducible experimentation rather than live plant operations. It is intentionally narrow in scope: synthetic data, simplified modeling assumptions, and rule-based detection make it easy to reason about and validate without external dependencies or production infrastructure.

Telemetry flows from a generator into CSV/JSON artifacts under `data/generated`, is validated against schema and relationship checks, and is then evaluated by the anomaly engine. Results are surfaced through the FastAPI app and persisted in SQLite as simulation runs and alarm records. A separate evaluation script compares detector output to ground-truth scenarios while keeping labels separate from the detection inputs.

A reviewer can run the project locally, generate telemetry, view the dashboard, submit a pump-speed simulation, and inspect the validation and anomaly outputs. The implementation is technically interesting because it combines synthetic equipment modeling, deterministic scenario injection, explainable detection rules, configuration hashing for traceability, and a local SQLite-backed workflow in a single Python application.

## Requirements-to-Implementation Status

| Requirement | Implementation evidence | Status |
|---|---|---|
| Industrial asset modeling | `app/generator.py` creates facilities, pumps, tanks, valves, pipes, sensors, operating modes, and telemetry records | Implemented |
| Synthetic telemetry generation | `generate_dataset()` produces deterministic CSV/JSON outputs under `data/generated` | Implemented |
| Structural validation | `app/validation.py` checks primary keys, foreign keys, pipe endpoints, tank capacity constraints, and telemetry validity | Implemented |
| Explainable rule-based anomaly detection | `app/engine.py` implements sensor-fault, pump-degradation, pressure-anomaly, and proxy leak checks | Implemented |
| Simulation execution | `app/main.py` exposes `/api/simulations` and stores configuration hash, seed, and output JSON | Implemented |
| Local persistence | SQLite tables `simulation_runs` and `alarms` are created in `industrialpulse.db` | Implemented |
| Browser dashboard | Root route returns an HTML dashboard with summary, telemetry, alarms, and simulation history | Implemented |
| Scenario evaluation | `evaluate_scenarios.py` loads `ground_truth.json` and matches alarms to labeled windows | Implemented |
| Reproducibility | `scripts/reproducibility_check.py` compares digests across generated runs with the same seed and telemetry count | Implemented |
| Production-safe industrial use | Documented limitations and synthetic-only assumptions in docs and README | Implemented |

## Key Capabilities

- Synthetic facility and equipment generation with stable IDs and deterministic seed control.
- Data validation for entity integrity, foreign keys, pipe endpoints, and tank capacity rules.
- Explainable anomaly detection for sensor freezes, negative physical readings, sustained high pressure, pump degradation, and flow-depression proxy scenarios.
- Simulation execution using a simplified pump-affinity-law estimate for speed changes.
- SQLite-backed persistence for alarm and simulation history.
- Browser dashboard and REST API for summary, telemetry, alarm, and simulation views.
- Scenario evaluation against separately stored ground-truth labels.
- Repeatable generation and reproducibility checks using a fixed seed.

## Architecture Overview

```mermaid
flowchart LR
    A[generate_data.py / app.generator.generate_dataset] --> B[data/generated CSV + JSON artifacts]
    B --> C[validate_dataset]
    B --> D[detect_anomalies]
    B --> E[FastAPI app /app/main.py]
    C --> E
    D --> F[(SQLite industrialpulse.db)]
    E --> G[Dashboard / browser UI]
    E --> H[REST API endpoints]
    H --> I[Simulation history + alarms]
    J[evaluate_scenarios.py] -. loads ground_truth.json .-> B
    J -. compares alarm windows to injected scenarios .-> D

    classDef process fill:#0f172a,stroke:#5eead4,color:#e2e8f0;
    class A,B,C,D,E,F,G,H,I,J process;
```

The production/application workflow is intentionally local and synchronous: the data is generated, validated, processed, and served by the same Python app. The evaluation workflow is separate: `evaluate_scenarios.py` loads the synthetic ground-truth labels and compares alarm time windows to expected issue windows without using those labels as detection features.

End-to-end flow:

1. The generator creates facility and equipment tables plus telemetry in `data/generated`.
2. `validate_dataset()` checks data integrity and relationship rules before the data is used downstream.
3. The detection engine inspects telemetry for process and sensor anomalies using explicit thresholds and deterministic logic.
4. The FastAPI app exposes summary, telemetry, alarms, and simulation endpoints and serves the browser dashboard.
5. Simulation requests are validated, a simplified affinity-law estimate is produced, and the run is stored with a `configuration_hash`.
6. Historical alarm and simulation records are persisted in SQLite for retrieval and review.
7. The evaluator compares detector outputs against separate ground-truth scenario labels to assess coverage and alignment.

## High-Level Design (HLD)

### System boundaries and responsibilities

The repository is organized into a small, local application rather than a multi-service system. The responsibilities are split by module:

- `app/generator.py` creates deterministic synthetic data and scenario windows.
- `app/validation.py` enforces integrity rules and basic engineering consistency checks.
- `app/engine.py` contains the rule engine for sensor and process anomaly detection.
- `app/main.py` hosts the FastAPI service, dashboard, and database writes.
- `evaluate_scenarios.py` performs separate evaluation against the stored scenario labels.
- `scripts/reproducibility_check.py` verifies deterministic generation for a fixed seed.

### Request and processing lifecycle

A typical request begins at the browser or API client, reaches `app/main.py`, and may trigger dataset generation and validation. For telemetry retrieval, the CSV file is read and returned; for alarm generation, the current dataset is sent through `detect_anomalies()`. For simulations, a pump ID and target speed percentage are accepted, the nominal performance is used to estimate a new flow and head, the run is stored in SQLite, and the result is returned as JSON.

### Data persistence and historical records

The local persistence is intentionally minimal. `industrialpulse.db` contains two main tables used by the demo application:

- `simulation_runs`: run ID, facility ID, raw configuration JSON, `configuration_hash`, seed, status, timestamps, and output JSON.
- `alarms`: alarm metadata such as component ID, alarm type, severity, rule ID, explanation, and creation timestamp.

These tables are append-only within the local prototype and support historical review in the dashboard.

### Configuration traceability

Each simulation stores the configuration as JSON and computes a SHA-256 `configuration_hash` over the serialized config. This makes it possible to trace which configuration produced a given run and compare distinct input states.

### Validation and error-handling strategy

Validation is explicit and deterministic. Before using telemetry or simulation inputs, the app checks required columns, data types, key integrity, and facility references. Invalid or unknown pump IDs raise HTTP 404 errors, and the validator returns `{"valid": ..., "errors": ...}` for dataset checks. The implementation is not a full distributed validation framework, but it enforces the relevant integrity checks for the demo workflow.

### Separation of evaluation and detection

The ground-truth labels are kept outside the detector’s primary input path. This is intentional: `ground_truth.json` is generated as a separate evaluation artifact, not as a feature used during inference. This reduces leakage risk and keeps the detector logic explainable and testable.

### Key design trade-offs

- Synthetic telemetry yields reproducibility and fast iteration, but it cannot represent real plant behavior.
- Rule-based detection is interpretable and easy to audit, but it is not a general ML classifier.
- SQLite keeps the project easy to run locally, but it is not a production-grade distributed database.
- The simulation model is intentionally simplified to prioritize understanding and traceability over hydraulic fidelity.

For a more detailed explanation of the intended architecture, see [docs/architecture.md](docs/architecture.md).

## Data Model

The application maintains a compact synthetic industrial data model centered on facility assets and telemetry. Stable IDs are string-based and prefixed for deterministic entity naming.

| Entity | Key fields | Relationship and notes |
|---|---|---|
| `facilities.csv` | `facility_id`, `name`, `status` | Root organizational unit for plant assets |
| `pumps.csv` | `pump_id`, `facility_id`, `nominal_flow_lps`, `shutoff_head_kpa`, `curve_k` | Facility-owned rotating equipment |
| `tanks.csv` | `tank_id`, `facility_id`, `capacity_liters`, `initial_volume_liters` | Storage asset with established capacity constraints |
| `valves.csv` | `valve_id`, `facility_id`, `opening_pct`, `state` | Control element within a facility |
| `pipes.csv` | `pipe_id`, `facility_id`, `from_node_id`, `to_node_id`, `diameter_mm`, `length_m` | Directed pipe links between valid nodes |
| `sensors.csv` | `sensor_id`, `facility_id`, `component_id`, `sensor_type`, `measurement_role` | Instrument metadata; one primary monitored component per sensor |
| `telemetry.csv` | `telemetry_id`, `sensor_id`, `timestamp`, `value`, `quality_status` | Time-series stream for each sensor |
| `operating_modes.csv` | `operating_mode_id`, `facility_id`, `mode_name`, `effective_from` | Operational mode metadata |
| `ground_truth.json` | scenario records with `issue_type`, `component_id`, windows | Separate evaluation labels; not a detector input |
| `simulation_runs` | `simulation_run_id`, `configuration_hash` | Persisted simulation attempts and output JSON |
| `alarms` | `alarm_id`, `rule_id`, `alarm_type`, `severity` | Event history generated by detection rules |

Important identifier semantics:

- `sensor_id` identifies the measuring instrument.
- `component_id` identifies the asset or facility the sensor monitors.
- A sensor-fault alarm therefore includes both the sensor and the monitored component when applicable.
- `ground_truth.json` uses legacy `component_id` semantics that depend on `issue_type`; this is documented in [docs/data_dictionary.md](docs/data_dictionary.md).

See [docs/data_dictionary.md](docs/data_dictionary.md) for full schema details and the documented relationship semantics.

## Detection and Simulation Methodology

### Detection rules

The detector in `app/engine.py` is intentionally rule-based and explainable. It does not rely on a trained model. The implemented checks include:

- `SENSOR_STUCK_VALUE`: repeated identical readings over a sustained window signal a likely frozen or stuck sensor.
- `NEGATIVE_PHYSICAL_READING`: negative values for flow, pressure, or level data are treated as non-physical.
- `SUSTAINED_HIGH_PRESSURE`: for a pressure sensor, a sustained run above 110% of the median of the first 20 timestamp-ordered readings triggers a pressure anomaly.
- `PUMP_PERFORMANCE_RATIO`: pump flow below 75% of the pump's nominal flow for at least 10 good readings indicates performance degradation.
- `FACILITY_FLOW_DEPRESSION_PROXY`: a multi-sensor facility-level depression is treated as a leak proxy rather than proof of a leak event.

These rules are parameterized in code and are meant to be auditable and calibrated, not treated as universal industrial standards.

### Simulation methodology

The simulation endpoint accepts a `pump_id` and `speed_pct`. It uses a simplified affinity-law estimate:

- `Q2 / Q1 ≈ N2 / N1`
- `H2 / H1 ≈ (N2 / N1)^2`

The app then predicts new flow and head from the pump nominal values and stores the result with the run metadata. This is a compact engineering approximation for demonstration purposes, not a hydraulic network solver or a validated plant model.

### Ground truth and evaluation

`ground_truth.json` contains deterministic injected scenario windows for the synthetic benchmark: pump degradation, sensor faults, leak-like flow suppression, and blockage-like pressure behavior. These labels are used only by `evaluate_scenarios.py` to compare detector outputs against expected issue windows. The detector itself never consumes those labels.

### Scope and limitations

The rules are valid only within the synthetic environment and the assumptions documented in [docs/simulation_assumptions.md](docs/simulation_assumptions.md). They do not establish causal proof of a physical process fault, and they cannot substitute for safety-reviewed process diagnostics or expert engineering judgment.

## Technology Stack and Design Rationale

| Component | Technology | Purpose | Reason for selection |
|---|---|---|---|
| Application logic | Python | Core generation, validation, detection, and simulation logic | Fast iteration and strong data-science ecosystem |
| HTTP API | FastAPI | Exposes summary, telemetry, alarm, and simulation endpoints | Lightweight, modern Python web API |
| Local persistence | SQLite | Stores simulation runs and alarm history | Self-contained, simple local deployment |
| Data processing | Pandas + NumPy | Telemetry shaping, filtering, and transformation | Familiar and efficient for tabular time-series workflow |
| Graph relationship logic | NetworkX | Pipe and topology-related processing support | Useful for structural relationship checks |
| Browser UI | HTML + JavaScript | Demonstrates dashboard interactions for summary and simulation results | Simple, dependency-free front-end |
| Testing | pytest | Validates generation, detector behavior, and scenario checks | Standard Python testing workflow |
| Reproducibility | hashlib + deterministic seed generation | Compares generated artifacts across runs | Supports repeatable synthetic experiments |

The design intentionally favors transparency and reproducibility over production scale. This is a prototype that demonstrates how a synthetic monitoring stack can be built and evaluated locally.

## Repository Structure

```text
IndustrialPulse-AI/
├── app/
│   ├── __init__.py
│   ├── engine.py
│   ├── generator.py
│   ├── main.py
│   └── validation.py
├── data/
│   └── generated/
│       ├── facilities.csv
│       ├── ground_truth.json
│       ├── negative_cases.json
│       ├── operating_modes.csv
│       ├── pipes.csv
│       ├── pumps.csv
│       ├── sensors.csv
│       ├── source_manifest.json
│       ├── tanks.csv
│       ├── telemetry.csv
│       └── valves.csv
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   ├── simulation_assumptions.md
│   └── ai_usage/
│       ├── ai_contribution_statement.md
│       └── prompt_history.md
├── scripts/
│   └── reproducibility_check.py
├── tests/
│   └── test_core.py
├── .gitignore
├── README.md
├── evaluate_scenarios.py
├── generate_data.py
├── industrialpulse.db
├── pytest.ini
└── requirements.txt
```

Key repository elements:

- `app/` holds the core application logic.
- `data/generated/` contains the generated baseline telemetry and metadata used by the project.
- `docs/` stores the architecture, schema, assumptions, and AI usage records.
- `tests/` contains the current validation suite for generation and detection behavior.
- `scripts/` contains the reproducibility checker.
- `evaluate_scenarios.py` is the separate evaluation workflow.

## Installation and Local Setup

### Prerequisites

- Python 3.10+
- `pip`
- A working terminal (PowerShell, Bash, or zsh)

### 1. Clone the repository

```bash
git clone https://github.com/ajaykuraparthi/IndustrialPulse-AI.git
cd IndustrialPulse-AI
```

### 2. Create a virtual environment

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Generate baseline data

```bash
python generate_data.py --telemetry 2000 --seed 20261022
```

For the project’s full synthetic dataset:

```bash
python generate_data.py --telemetry 100000 --seed 20261022
```

## Running the Application

Start the backend from the repository root:

```bash
uvicorn app.main:app --reload
```

Then open:

- Dashboard: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

The application will create `data/generated` artifacts automatically when needed and will initialize SQLite tables on first use.

## API Surface

The app exposes several operational endpoints:

- `GET /api/summary`: dataset counts and validation result
- `GET /api/telemetry?limit=100`: sample telemetry records
- `GET /api/alarms`: current alert history
- `POST /api/simulations`: run a simulation with a `pump_id` and `speed_pct`
- `GET /api/simulations`: list persisted simulation runs
- `/`: browser dashboard

Example simulation payload:

```json
{
  "pump_id": "PUMP-001",
  "speed_pct": 80,
  "seed": 20261022
}
```

## Validation and Verification

### Automated tests

```bash
python -m pytest -q
```

The current suite validates:

- dataset generation counts and relationships
- separate ground-truth storage from detector inputs
- stuck-sensor detection
- pump degradation detection
- negative physical reading detection
- facility-level leak proxy detection
- sustained high pressure detection

As of the repository state checked here, the suite passes:

- `12 passed` (with one dependency warning from pytest on this environment)

### Scenario evaluation

```bash
python evaluate_scenarios.py
```

This script compares alarm windows to injected ground-truth issue windows and reports exact and facility-level proxy matches. It is a tool for evaluation and traceability, not a production-vetted score card.

### Reproducibility check

```bash
python scripts/reproducibility_check.py --telemetry 1000
```

This confirms that, with the same seed and telemetry count, the generator produces equivalent artifacts. The check is intentionally local and deterministic for the synthetic dataset.

## Known Limitations

- The project is a synthetic demonstration and does not ingest real plant data.
- The anomaly rules are illustrative and not validated against operational safety thresholds.
- The pump simulation is a simplified affinity-law approximation; it does not solve a full hydraulic network.
- The leak and blockage detection logic produces proxy-level conclusions when the data only supports aggregate facility-level signals.
- SQLite is suitable for a local demo but is not a production-grade industrial historian or enterprise database.

## Responsible Use

IndustrialPulse AI should be used as a learning, validation, and demonstration tool. It is not a certified industrial control system and should not be treated as a replacement for operational monitoring, safety instrumentation, or engineering review.

The repository documentation in [docs/architecture.md](docs/architecture.md), [docs/data_dictionary.md](docs/data_dictionary.md), and [docs/simulation_assumptions.md](docs/simulation_assumptions.md) should be treated as the authoritative local explanation of the implemented behavior.

## Final Note

This repository is strongest as a compact, explainable, end-to-end synthetic industrial monitoring prototype. It demonstrates how deterministic data generation, explicit validation, transparent anomaly checks, and a local API/dashboard workflow can be combined into a practical engineering MVP without introducing unnecessary infrastructure complexity.
