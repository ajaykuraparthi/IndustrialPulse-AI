# IndustrialPulse AI — High-Level Design (HLD)

## 1. Overview

IndustrialPulse AI is a lightweight industrial monitoring and simulation platform designed to demonstrate telemetry validation, rule-based anomaly detection, simulation execution, and historical event tracking.

The application processes synthetic industrial telemetry, evaluates it against configurable detection rules, exposes results through REST APIs, and persists simulation runs and alarms for historical review through a browser-based dashboard.

The system is intended for demonstration and evaluation purposes. It does not replace validated industrial monitoring, hydraulic simulation, or safety-critical control systems.

## 2. High-Level Architecture

```text
                ┌────────────────────────┐
                │ Synthetic Data Generator│
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │ Data Validation Layer  │
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │ Rule-Based Detection   │
                │ Engine                 │
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │ Simulation / Processing│
                │ Workflow               │
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │ FastAPI REST API       │
                └────────────┬───────────┘
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
       ┌──────────────────┐  ┌──────────────────┐
       │ SQLite Persistence│  │ Browser Dashboard│
       │                  │  │                  │
       │ Runs, Alarms,    │  │ Results, Alarms, │
       │ Historical Data  │  │ Simulation Views │
       └──────────────────┘  └──────────────────┘
```

*Note: This diagram represents the logical processing flow. The actual implementation may organize simulation processing, API handling, and persistence differently.*

## 3. Core Components

### 3.1. Synthetic Data Generator

Generates simulated industrial telemetry for the demonstration environment.

The generated data represents measurements from industrial entities such as pumps, tanks, valves, pipes, and sensors.

Its purpose is to provide repeatable input for evaluating monitoring and simulation workflows without requiring live industrial equipment or external telemetry sources.

### 3.2. Data Validation Layer

Validates incoming requests and telemetry data before processing.

Responsibilities include:
- Checking required fields and supported data types.
- Enforcing applicable schema and range constraints.
- Rejecting invalid requests with appropriate errors.
- Preventing invalid inputs from silently entering downstream processing.

The exact validation rules depend on the implemented schemas and endpoints.

### 3.3. Rule-Based Detection Engine

Evaluates telemetry against configured conditions to identify potential anomalies.

Detection results may include conditions such as abnormal measurements or deviations from configured thresholds.

Ground-truth labels are maintained separately from detector inputs to reduce the risk of evaluation leakage.

The detector uses simplified, explainable rules rather than a trained machine-learning model. Detection results should therefore be interpreted within the scope of those rules and the synthetic evaluation scenarios.

### 3.4. Simulation and Processing Workflow

Coordinates the processing of a simulation request and its associated configuration and results.

A simulation run provides a traceable record of a particular execution. The `configuration_hash` identifies the configuration associated with that run, allowing configurations to be compared and traced.

Historical simulation runs and alarms are appended to persistent records rather than intentionally replacing earlier run history.

### 3.5. FastAPI REST API

Provides the application interface between the dashboard, processing logic, and persistence layer.

The API is responsible for:
- Accepting supported requests.
- Invoking validation and processing logic.
- Returning simulation results and relevant historical records.
- Exposing errors for invalid or unsuccessful operations.

FastAPI provides request handling and schema validation capabilities. Application-specific business rules are implemented separately where applicable.

### 3.6. SQLite Persistence Layer

Stores application data needed for simulation history and event tracking.

The persistence layer supports retaining simulation runs, alarms, and associated information for subsequent retrieval.

SQLite keeps the demonstration self-contained and avoids requiring a separate database server.

The application should not be interpreted as having production-grade database scaling, backup, or recovery guarantees.

### 3.7. Browser Dashboard

Provides a lightweight interface for interacting with the monitoring application.

Depending on the implemented features, users can inspect simulation results, review alarms, and access historical information.

The dashboard consumes backend API responses rather than independently determining anomaly results.

## 4. Data Flow

A typical processing workflow is:

1. Synthetic telemetry is generated for the demonstration environment.
2. Input data and simulation requests are validated.
3. Valid telemetry is processed by the applicable detection rules.
4. The simulation workflow produces its results and associated events.
5. The API exposes the relevant outputs to the dashboard and other supported clients.
6. Simulation runs and alarms are persisted for historical retrieval.
7. The dashboard presents the returned results and available history.

Ground-truth labels are kept separate from the detector's input data and are used for evaluation rather than to determine detection outcomes.

## 5. Data Integrity and Traceability

The design incorporates several measures to improve traceability and evaluation integrity:

- **Input validation:** Rejects unsupported or invalid inputs according to the implemented validation rules.
- **Separate ground truth:** Keeps evaluation labels separate from detector inputs.
- **Configuration traceability:** Uses `configuration_hash` to identify a simulation configuration.
- **Historical records:** Retains prior simulation runs and alarms instead of intentionally overwriting run history.
- **Repeatability:** Supports controlled evaluation using synthetic data and reproducibility procedures where configured.
- **Error handling:** Provides feedback for invalid requests and unsuccessful operations through the relevant application interfaces.

These measures support development and evaluation; they do not independently establish production-grade reliability or safety.

## 6. Technology Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Backend API | Python, FastAPI | Request handling and API responses |
| Data processing | Python | Telemetry processing and rule evaluation |
| Persistence | SQLite | Simulation and event history |
| Frontend | Browser-based dashboard | Visualization and user interaction |
| Input data | Synthetic telemetry | Repeatable demonstration scenarios |
| Verification | Automated tests and evaluation scripts | Checking implemented behavior |

The table describes the project's intended architectural responsibilities. Individual implementation details should be confirmed against the submitted repository.

## 7. Design Decisions

### Synthetic Data

Synthetic data makes the project easier to run and evaluate without access to industrial infrastructure. It also allows controlled demonstration scenarios.

**Trade-off:** Synthetic scenarios may not represent the full variability, noise, and complexity of real industrial environments.

### Explainable Rule-Based Detection

Explicit rules make the detection logic easier to understand, inspect, and debug.

**Trade-off:** Fixed rules may fail to detect conditions outside their defined thresholds and assumptions.

### SQLite

SQLite provides a simple persistence mechanism for a self-contained demonstration.

**Trade-off:** A larger, concurrent production deployment may require a different persistence architecture and additional operational controls.

### Configuration Hashing

Associating a configuration hash with a simulation run improves traceability when comparing executions.

**Trade-off:** A hash is only useful for reproducibility when configuration serialization, relevant inputs, and other execution dependencies are handled consistently.

## 8. Current Scope and Limitations

IndustrialPulse AI is a demonstration platform, not a validated industrial control or engineering system.

Known limitations include:

- Telemetry and evaluation scenarios are synthetic.
- Detection is based on simplified rules and thresholds.
- Some scenario outcomes may use facility-level indicators as proxies rather than exact equipment-level fault identification.
- The simplified simulation logic does not constitute a complete hydraulic solver.
- The implementation does not establish production-grade alarm lifecycle management or safety validation.
- Reproducibility depends on the inputs, configuration, and execution conditions covered by the implemented procedures.

Further engineering work would be required before considering deployment in a real industrial environment.

## 9. Summary

IndustrialPulse AI combines synthetic telemetry, input validation, explainable rule-based detection, simulation workflows, REST APIs, SQLite persistence, and a browser dashboard into a compact industrial monitoring demonstration.

Its principal goals are to make the processing workflow understandable, retain traceable simulation history, and support repeatable evaluation while explicitly documenting the assumptions and limitations of the implementation.