# IndustrialPulse AI
### Synthetic Industrial Monitoring, Anomaly Detection, Data Validation & Simulation

IndustrialPulse AI is a Python-based industrial monitoring MVP designed to model industrial facilities, generate synthetic equipment telemetry, identify potential anomalies, validate equipment relationships, and simulate simplified operational changes.

The system models interconnected industrial components, including facilities, pumps, tanks, valves, pipes, and sensors. It combines deterministic synthetic data generation, explainable rule-based anomaly detection, structural validation, SQLite persistence, and a FastAPI application with a lightweight browser dashboard.

> **Important:** IndustrialPulse AI is an educational and experimental synthetic engineering model. It is not a safety-certified industrial control system, a validated digital twin, or a replacement for professional industrial monitoring systems.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation and Setup](#installation-and-setup)
- [Generating Synthetic Data](#generating-synthetic-data)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Anomaly Detection](#anomaly-detection)
- [Data Validation](#data-validation)
- [Operational Simulation](#operational-simulation)
- [Testing](#testing)
- [Reproducibility](#reproducibility)
- [Data Model](#data-model)
- [Engineering Assumptions](#engineering-assumptions)
- [Evaluation Strategy](#evaluation-strategy)
- [Limitations and Future Improvements](#limitations-and-future-improvements)
- [Responsible Use](#responsible-use)

---

## Project Overview

Industrial facilities contain interconnected equipment whose operating conditions change over time. Abnormal pressure, unexpected flow changes, degraded pump performance, and faulty sensors can indicate potential operational problems.

IndustrialPulse AI explores how a lightweight monitoring platform can represent these components, generate synthetic operating data, and apply transparent detection rules to identify potential abnormalities.

The project focuses on five areas:

1. **Industrial asset modeling:** Represent facilities and their associated equipment.
2. **Synthetic telemetry generation:** Generate repeatable equipment readings for development and testing.
3. **Anomaly detection:** Apply interpretable rules to identify potential equipment and sensor abnormalities.
4. **Data validation:** Check structural relationships and selected engineering constraints.
5. **Operational simulation:** Explore simplified equipment operating changes and persist simulation records.

The application exposes its functionality through a FastAPI backend and provides a browser-based interface for interacting with the system.

## Key Features

### 1. Industrial Asset Modeling

The synthetic environment includes:

- Facilities
- Pumps
- Tanks
- Valves
- Pipes
- Sensors
- Operating modes
- Telemetry records
- Alarms
- Simulation runs

Equipment relationships are represented through identifiers and pipe connections.

### 2. Deterministic Synthetic Data Generation

The generator supports seeded data generation so that the same configuration can be used for repeatable development and testing.

The default full-data workflow generates 100,000 telemetry records.

Example:

```powershell
python generate_data.py --telemetry 100000 --seed 20261022
```

The generated dataset is stored locally under `data/generated/`.

### 3. Explainable Anomaly Detection

The detection engine uses configurable, rule-based checks to identify potential issues, including:

- Sensor faults
- Pump performance degradation
- Abnormal flow residuals that may indicate leakage or other flow inconsistencies
- Potential blockage-related conditions, where supported by the implemented rules

Detection thresholds are defined in the application code.

These rules are intended to be understandable and inspectable rather than opaque predictions from a machine-learning model.

### 4. Structural Data Validation

The validation module checks selected properties of the generated industrial environment, including:

- Equipment identifiers and relationships
- Pipe endpoint references
- Selected tank capacity and level constraints
- Basic consistency between modeled components

The exact guarantees are limited to the checks implemented in the validation module.

### 5. Operational Simulation

The application provides a simulation API for submitting equipment operating changes.

For example, a request can specify a pump and a target speed. The application can then process the request according to its implemented simulation logic and persist a simulation record.

The simulation is simplified and should not be interpreted as a full hydraulic-network calculation.

### 6. API and Dashboard

The FastAPI application provides HTTP endpoints for retrieving summary information, telemetry, alarms, and simulation records.

A lightweight browser dashboard is available for inspecting the application.

### 7. Automated Testing

Pytest is used to test selected aspects of the project.

The current test suite covers basic dataset generation, ground-truth separation, and an anomaly-detection rule.

Passing these tests does not establish that all anomaly types or simulation behaviors have been validated.

---

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic and data generation |
| FastAPI | HTTP API |
| Uvicorn | ASGI application server |
| SQLite | Local persistence for supported application records |
| Pandas | Tabular data handling, where used by the implementation |
| Pytest | Automated testing |
| CSV and JSON | Synthetic data and metadata storage |

The application is designed as a lightweight MVP that can run locally without requiring a cloud deployment.

---

## System Architecture

The system is organized into several logical components.

```text
                Synthetic Data Generator
                          |
                          v
                 Industrial Data Files
                   CSV / JSON
                          |
             +------------+------------+
             |                         |
             v                         v
      Data Validation          Anomaly Detection
             |                         |
             +------------+------------+
                          |
                          v
                   FastAPI Backend
                          |
             +------------+------------+
             |                         |
             v                         v
       Browser Dashboard        SQLite Persistence
             |                         |
             +------------+------------+
                          |
                          v
               Summary and API Results
```

### Component Responsibilities

**Data generator — `app/generator.py`**

Creates synthetic industrial entities, relationships, telemetry, and scenario-related artifacts.

**Anomaly engine — `app/engine.py`**

Applies implemented detection rules to identify potential abnormal conditions.

**Validation module — `app/validation.py`**

Checks selected structural and engineering constraints.

**Application API — `app/main.py`**

Exposes application functionality through FastAPI, manages supported persistence operations, and serves the browser interface.

**Automated tests — `tests/test_core.py`**

Exercises selected generation, data separation, and anomaly-detection behavior.

**Reproducibility utility — `scripts/reproducibility_check.py`**

Provides a utility for checking reproducibility. Its behavior should be verified using the command shown in the testing section.

---

## Project Structure

The main repository structure is expected to resemble the following:

```text
IndustrialPulse-AI/
├── app/
│   ├── __init__.py
│   ├── generator.py
│   ├── engine.py
│   ├── validation.py
│   └── main.py
├── tests/
│   └── test_core.py
├── scripts/
│   └── reproducibility_check.py
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   └── simulation_assumptions.md
├── generate_data.py
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

The exact files in the repository may vary as the project evolves.

Generated data is excluded from Git by the current `.gitignore` configuration. It is created locally when the generator runs.

---

## Requirements

- Python 3.10 or later
- pip
- Git, if cloning the repository
- A terminal such as Windows PowerShell
- A modern web browser

The application is intended to run locally on Windows, Linux, or macOS, subject to dependency compatibility.

---

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/ajaykuraparthi/IndustrialPulse-AI.git
cd IndustrialPulse-AI
```

### 2. Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can temporarily allow local activation scripts in the current terminal session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Then activate the environment again:

```powershell
.\.venv\Scripts\Activate.ps1
```

**Linux or macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

With the virtual environment activated, run:

```bash
python -m pip install -r requirements.txt
```

### 4. Generate the dataset

Generate a smaller dataset first to check that the generator runs:

```bash
python generate_data.py --telemetry 2000 --seed 20261022
```

For the full synthetic dataset, run:

```bash
python generate_data.py --telemetry 100000 --seed 20261022
```

The generated files should appear under:

```text
data/generated/
```

Because generated files are ignored by Git, each developer should generate the required data locally.

---

## Generating Synthetic Data

The generator creates a synthetic industrial environment with interconnected equipment and telemetry records.

The current 100,000-record configuration has produced the following dataset counts:

| Entity | Count |
|---|---:|
| Facilities | 3 |
| Pumps | 20 |
| Tanks | 30 |
| Valves | 60 |
| Pipes | 107 |
| Sensors | 53 |
| Telemetry records | 100,000 |

These counts describe the generated dataset configuration used during development. They are not measurements from a real industrial facility.

### Seeded Generation

The `--seed` argument controls the random seed used by the generator.

Example:

```bash
python generate_data.py --telemetry 100000 --seed 20261022
```

For reproducible results, use the same seed, telemetry count, software dependencies, and generation configuration.

Reproducibility should be verified against the generated outputs rather than assumed solely from using a fixed seed.

### Generated Artifacts

The generator creates synthetic data files under `data/generated/`.

Depending on the generation configuration, these artifacts include:

- Industrial component tables
- Telemetry records
- Ground-truth scenario records
- Negative test cases
- Source or generation metadata

Ground-truth artifacts are intended for evaluation and testing. They should remain separate from the features supplied to anomaly-detection functions to reduce the risk of data leakage.

---

## Running the Application

Make sure the virtual environment is activated and the dependencies are installed.

Start the application from the repository root:

```bash
uvicorn app.main:app --reload
```

When the server starts successfully, the application should be available at the following local addresses.

### Browser Dashboard

http://127.0.0.1:8000

### Interactive API Documentation

http://127.0.0.1:8000/docs

### OpenAPI Schema

http://127.0.0.1:8000/openapi.json

The server must remain running while you use these local addresses.

The `--reload` option is intended for development, not production deployment.

---

## API Documentation

The application exposes the following documented endpoints.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/summary` | Retrieve dataset and application summary information |
| GET | `/api/alarms` | Retrieve available alarm records |
| GET | `/api/telemetry?limit=100` | Retrieve a limited set of telemetry records |
| POST | `/api/simulations` | Submit an equipment simulation request |
| GET | `/api/simulations` | Retrieve available simulation records |

Use the interactive API documentation at `/docs` to inspect request schemas, execute requests, and review responses.

### Example: Retrieve the Summary

Send a GET request to:

```text
http://127.0.0.1:8000/api/summary
```

A successful response includes information about the dataset, validation results, and available application records.

Example structure:

```json
{
  "counts": {
    "facilities": 3,
    "pumps": 20,
    "tanks": 30,
    "valves": 60,
    "pipes": 107,
    "sensors": 53,
    "telemetry": 100000,
    "active_alarms": 0,
    "simulation_runs": 0
  },
  "validation": {
    "valid": true,
    "errors": []
  }
}
```

The exact response depends on the current local dataset and application state. The example is illustrative.

### Example: Retrieve Telemetry

Send a GET request to:

```text
http://127.0.0.1:8000/api/telemetry?limit=100
```

The endpoint returns a limited set of telemetry records according to the implemented response schema.

### Example: Retrieve Alarms

Send a GET request to:

```text
http://127.0.0.1:8000/api/alarms
```

The response contains available alarm records. An empty result does not necessarily indicate a malfunction; it may mean that no alarms have been generated or persisted.

### Example: Submit a Simulation

Send a POST request to:

```text
http://127.0.0.1:8000/api/simulations
```

Example request body:

```json
{
  "pump_id": "PUMP-001",
  "speed_pct": 80
}
```

This example assumes that `PUMP-001` exists in the generated dataset and that the request matches the API's expected schema.

Use `/docs` to confirm the current request fields and response structure.

---

## Anomaly Detection

IndustrialPulse AI includes a rule-based anomaly-detection engine.

Rule-based detection is used because its decisions can be inspected and explained. Rather than relying on an opaque model, the application applies defined checks to selected telemetry and operational conditions.

### Detection Categories

The project is designed to investigate the following types of abnormalities.

#### Sensor Faults

Sensor readings may indicate a potential sensor fault when they satisfy the configured conditions implemented in the detection engine.

#### Pump Performance Degradation

The detector reports a pump-specific alarm only when at least 10 consecutive good-quality flow readings from its sensor are below 75% of that pump's nominal flow. A concurrent multi-pump facility flow depression is reported as an aggregate proxy instead of separate unsupported pump diagnoses.

#### Facility Flow Depression Proxy

The generated leak scenario reduces inlet- and outlet-tagged pump flows together; it does not provide an independent paired flow balance. The detector flags sustained sub-nominal normalized flow across multiple facility pump sensors as a screening proxy only.

This proxy does not establish that a leak exists or identify its location.

#### Blockage-Related Conditions

At least 10 consecutive readings above 110% of the median of a pressure sensor's first 20 timestamp-ordered readings constitute a pressure anomaly. Pressure is measured at facility level in this dataset, so the alarm does not identify `PIPE-001` or prove a physical blockage.

Sensor-fault alarms include both the sensor ID and its monitored component ID. Suspect-quality readings can trigger sensor-quality rules but are excluded from pump and facility process rules.

### Detection Thresholds

Detection thresholds are implemented as configurable constants in `app/engine.py`.

These thresholds are illustrative. They have not been established as universally valid industrial operating limits.

### Important Distinction

The presence of a fault scenario in the synthetic dataset does not guarantee that the anomaly detector will identify it.

Detection coverage, false positives, false negatives, and detection timing must be measured through testing.

---

## Data Validation

The validation module checks selected properties of the synthetic industrial environment.

The validation checks include supported constraints involving:

- Equipment identifiers
- Component relationships
- Pipe endpoint references
- Tank capacity and level conditions
- Basic consistency of generated records

A validation response such as:

```json
{
  "valid": true,
  "errors": []
}
```

indicates that the checks implemented by the current validator did not report errors for the data it examined.

It does not establish that the model is physically accurate or that every possible data-integrity issue has been ruled out.

### Negative Test Cases

Deliberately invalid cases are kept separate from the baseline generated dataset.

Examples include invalid tank-level conditions and invalid pipe references, where produced by the generator.

Keeping negative cases separate allows invalid inputs to be used for testing without silently contaminating the normal baseline dataset.

---

## Operational Simulation

The project exposes a simulation API for evaluating simplified changes to equipment operating conditions.

A simulation request can specify a pump and a target speed.

Example:

```json
{
  "pump_id": "PUMP-001",
  "speed_pct": 80
}
```

The API uses the implemented simulation logic to process the request and store supported simulation records.

### Simulation Scope

The current implementation is a simplified scenario model. It is not a full hydraulic-network solver.

The simulation should not be assumed to capture all interactions among:

- Pump curves
- Pipe friction
- Valve characteristics
- Fluid properties
- Tank levels
- Network pressure
- Transient operating behavior

Any outputs must be interpreted in the context of the model's assumptions and implemented calculations.

---

## Testing

Run tests from the repository root with the virtual environment activated:

```bash
python -m pytest -q
```

### Current Test Coverage

The automated suite covers selected behavior, including:

- Synthetic dataset generation and data relationships
- Separation of ground-truth artifacts from detector features
- Sensor-fault, pump-degradation, negative-reading, facility-flow-proxy, and sustained-pressure rules
- Exclusion of suspect readings from process alarms
- Malformed telemetry handling
- Exact sensor-target and facility-proxy scenario matching

### Additional Recommended Tests

Further tests should cover:

- Invalid equipment references
- Invalid tank-level conditions
- Invalid simulation requests
- Valid simulation requests
- Database persistence
- Boundary values for telemetry and simulation inputs

The project should not be considered fully validated until the additional relevant behaviors have been tested.

---

## Reproducibility

Reproducibility is important when evaluating synthetic data and anomaly-detection behavior.

The project includes a reproducibility-checking utility:

```bash
python scripts/reproducibility_check.py --telemetry 1000
```

This command should be used to verify the behavior implemented by the utility in the current revision.

For a reproducibility assessment, compare the generated outputs using the same:

- Random seed
- Telemetry count
- Generator version
- Dependency versions
- Configuration
- Input files, where applicable

A fixed random seed alone does not guarantee byte-for-byte identical output if other generation settings, software versions, or output ordering change.

---

## Data Model

The synthetic environment contains the following primary entities.

| Entity | Primary Key | Key Relationships | Important Units |
|---|---|---|---|
| Facility | `facility_id` | Parent of associated equipment | — |
| Pump | `pump_id` | References a facility | Flow: L/s; pressure: kPa |
| Tank | `tank_id` | References a facility | Volume: L |
| Valve | `valve_id` | References a facility | Opening: % |
| Pipe | `pipe_id` | References a facility and endpoint nodes | Diameter: mm; length: m |
| Sensor | `sensor_id` | References a facility and component | Depends on sensor type |
| Telemetry | `telemetry_id` | References a sensor | Depends on measurement type |
| OperatingMode | `operating_mode_id` | References a facility | Effective timestamps: UTC |
| Alarm | `alarm_id` | May reference a simulation run | Severity depends on schema |
| SimulationRun | `simulation_run_id` | References a facility | Seed and configuration metadata |

These entities form a simplified synthetic representation of industrial equipment and its operating data.

---

## Engineering Assumptions

### Units

The synthetic model uses the following units:

- Flow: liters per second (L/s)
- Pressure: kilopascals (kPa)
- Tank volume: liters (L)
- Pipe diameter: millimeters (mm)
- Pipe length: meters (m)
- Valve opening: percentage

These units are model conventions and should be checked before incorporating any external data.

### Directed Topology

The synthetic topology represents pipe connections as a directed graph.

Pipe endpoints are expected to reference valid component nodes in the node registry used by the application.

### Simplified Pump Curve

The documented pump approximation is:

```text
head = shutoff_head_kpa - curve_k * flow_lps**2
```

This is a simplified relationship used for modeling purposes. It is not a substitute for a manufacturer-provided pump curve or a validated hydraulic model.

### Tank Balance

The simplified tank-volume balance is:

```text
volume[t+1] = volume[t] + (inflow - outflow) * dt_seconds
```

The relationship assumes compatible flow and time units and must be constrained by the tank's physical limits.

### Detection Thresholds

Thresholds are configurable constants in the detection engine.

They should be calibrated and validated against representative operating data before any real-world use.

### Simulation Assumptions

Simulations are simplified scenario comparisons rather than full hydraulic-network solutions.

Their outputs should be interpreted as results of the implemented model, not predictions guaranteed to match real industrial equipment.

---

## Evaluation Strategy

The current project provides synthetic ground-truth artifacts intended to support systematic evaluation of anomaly detection.

A complete evaluation should compare detector outputs with ground-truth scenarios without supplying the ground-truth labels as detector inputs.

Run the current deterministic scenario screen with:

```powershell
python evaluate_scenarios.py
```

The evaluator checks alarm time-window overlap and documented target relationships. Pump and sensor targets can be exact matches; leak and pipe blockage results are labeled facility-level proxies. It lists unmatched alarms as unexpected. These are screening counts, not precision, recall, or F1 metrics.

### Recommended Metrics

**Precision**

The proportion of detected anomalies that correspond to ground-truth anomalies under the chosen matching rules.

**Recall**

The proportion of ground-truth anomalies detected by the system.

**F1 Score**

The harmonic mean of precision and recall.

**False-Positive Rate**

The frequency with which normal conditions are incorrectly classified as anomalous, using a clearly defined denominator.

**Detection Delay**

The elapsed time between the beginning of a ground-truth scenario and the first qualifying detection.

**Scenario-Level Detection Rate**

The proportion of injected scenarios detected within their expected evaluation windows.

### Evaluation Considerations

Evaluation should define:

- What constitutes an anomaly
- How detections are matched to ground-truth scenarios
- The time window used for matching
- How repeated alarms are handled
- How normal operating conditions are sampled
- How multiple detections for the same scenario are counted

Metrics should be reported only after the evaluation has actually been implemented and executed.

No detection-accuracy percentage is claimed in this README.

---

## Limitations and Future Improvements

IndustrialPulse AI is an MVP. The following limitations should be considered.

### Current Limitations

- The dataset is synthetic and does not establish real-world detection performance.
- Detection rules use illustrative thresholds.
- Flow residuals are approximate and depend on available sensor measurements and storage changes.
- Similar symptoms may have different causes, limiting fault identification.
- The simulation model does not solve the full hydraulic network.
- Validation covers only the constraints implemented in the validator.
- Automated tests cover only selected behaviors.
- No measured precision, recall, F1 score, or detection-delay benchmark is claimed here.
- The browser dashboard is intentionally lightweight.
- The application is not intended for safety-critical operational control.

### Future Improvements

Potential extensions include:

1. Add comprehensive scenario-level anomaly evaluation.
2. Measure precision, recall, F1 score, and detection delay.
3. Improve physical consistency in synthetic telemetry generation.
4. Expand mass-balance and network-consistency validation.
5. Add tests for all injected fault scenarios.
6. Improve simulation behavior and validate its assumptions.
7. Add richer alarm history and equipment-level visualizations.
8. Introduce structured logging and clearer error responses.
9. Improve dataset provenance and reproducibility checks.
10. Add configurable operating thresholds and scenario parameters.
11. Benchmark larger datasets and optimize data access.
12. Validate model assumptions against appropriate engineering references and real data, where available.

---

## Responsible Use

IndustrialPulse AI is intended for:

- Educational exploration
- Synthetic data generation
- Software engineering demonstrations
- Testing anomaly-detection concepts
- Experimenting with basic industrial data validation
- Demonstrating a lightweight API and simulation workflow

It must not be used as the sole basis for:

- Industrial safety decisions
- Real equipment control
- Emergency response
- Maintenance decisions requiring validated diagnostic evidence
- Claims of production-grade digital-twin accuracy

Any real-world application would require domain-expert review, appropriate engineering validation, representative data, cybersecurity assessment, and safety analysis.

---

## Author

**Ajay Kuraparthi**

GitHub: https://github.com/ajaykuraparthi

**Project:** IndustrialPulse AI

**Purpose:** Synthetic industrial monitoring, anomaly detection, validation, and operational simulation MVP.

---

## Final Note

IndustrialPulse AI demonstrates an initial software architecture for representing synthetic industrial assets, generating telemetry, validating selected data relationships, applying explainable anomaly-detection rules, and exposing functionality through an API.

Its results should be interpreted according to the implemented logic, synthetic data assumptions, and measured test coverage.