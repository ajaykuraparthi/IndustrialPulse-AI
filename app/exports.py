"""Deterministic exports for generated seed data and persisted simulation results."""
from __future__ import annotations

import csv
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from .validation import validate_dataset

SEED_SCHEMA = (
    """CREATE TABLE facilities (
      facility_id TEXT PRIMARY KEY, name TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('active', 'inactive')))""",
    """CREATE TABLE pumps (
      pump_id TEXT PRIMARY KEY, facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
      nominal_flow_lps REAL NOT NULL CHECK(nominal_flow_lps > 0),
      shutoff_head_kpa REAL NOT NULL CHECK(shutoff_head_kpa > 0),
      curve_k REAL NOT NULL CHECK(curve_k > 0),
      status TEXT NOT NULL CHECK(status IN ('active', 'inactive')),
      UNIQUE(pump_id, facility_id))""",
    """CREATE TABLE tanks (
      tank_id TEXT PRIMARY KEY, facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
      capacity_liters INTEGER NOT NULL CHECK(capacity_liters > 0),
      initial_volume_liters INTEGER NOT NULL CHECK(initial_volume_liters >= 0 AND initial_volume_liters <= capacity_liters),
      status TEXT NOT NULL CHECK(status IN ('active', 'inactive')))""",
    """CREATE TABLE valves (
      valve_id TEXT PRIMARY KEY, facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
      opening_pct INTEGER NOT NULL CHECK(opening_pct BETWEEN 0 AND 100),
      state TEXT NOT NULL CHECK(state IN ('open', 'closed')),
      status TEXT NOT NULL CHECK(status IN ('active', 'inactive')))""",
    """CREATE TABLE components (
      component_id TEXT PRIMARY KEY, facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
      component_type TEXT NOT NULL CHECK(component_type IN ('facility', 'pump', 'tank', 'valve')),
      UNIQUE(component_id, facility_id))""",
    """CREATE TABLE pipes (
      pipe_id TEXT PRIMARY KEY, facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
      from_node_id TEXT NOT NULL, to_node_id TEXT NOT NULL,
      diameter_mm INTEGER NOT NULL CHECK(diameter_mm > 0),
      length_m REAL NOT NULL CHECK(length_m > 0),
      status TEXT NOT NULL CHECK(status IN ('active', 'inactive')),
      CHECK(from_node_id <> to_node_id),
      FOREIGN KEY(from_node_id, facility_id) REFERENCES components(component_id, facility_id),
      FOREIGN KEY(to_node_id, facility_id) REFERENCES components(component_id, facility_id))""",
    """CREATE TABLE sensors (
      sensor_id TEXT PRIMARY KEY, facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
      component_id TEXT NOT NULL,
      sensor_type TEXT NOT NULL CHECK(sensor_type IN ('flow', 'pressure', 'level')),
      unit TEXT NOT NULL CHECK(unit IN ('L/s', 'kPa', 'L')),
      measurement_role TEXT NOT NULL CHECK(measurement_role IN ('inlet', 'outlet', 'level', 'pressure')),
      status TEXT NOT NULL CHECK(status IN ('active', 'inactive')),
      CHECK((sensor_type = 'flow' AND unit = 'L/s' AND measurement_role IN ('inlet', 'outlet'))
        OR (sensor_type = 'pressure' AND unit = 'kPa' AND measurement_role = 'pressure')
        OR (sensor_type = 'level' AND unit = 'L' AND measurement_role = 'level')),
      FOREIGN KEY(component_id, facility_id) REFERENCES components(component_id, facility_id),
      UNIQUE(sensor_id, facility_id, component_id, sensor_type, unit, measurement_role))""",
    """CREATE TABLE operating_modes (
      operating_mode_id TEXT PRIMARY KEY,
      facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
      mode_name TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT,
      status TEXT NOT NULL CHECK(status IN ('active', 'inactive')),
      CHECK(effective_to IS NULL OR effective_to >= effective_from))""",
    """CREATE TABLE telemetry (
      telemetry_id TEXT PRIMARY KEY,
      sensor_id TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
      component_id TEXT NOT NULL,
      sensor_type TEXT NOT NULL, unit TEXT NOT NULL, measurement_role TEXT NOT NULL,
      value REAL NOT NULL, quality_status TEXT NOT NULL CHECK(quality_status IN ('good', 'suspect')),
      UNIQUE(sensor_id, timestamp),
      FOREIGN KEY(sensor_id, facility_id, component_id, sensor_type, unit, measurement_role)
        REFERENCES sensors(sensor_id, facility_id, component_id, sensor_type, unit, measurement_role))""",
)

SEED_TABLES = (
    ("facilities", "facility_id, name, status"),
    ("pumps", "pump_id, facility_id, nominal_flow_lps, shutoff_head_kpa, curve_k, status"),
    ("tanks", "tank_id, facility_id, capacity_liters, initial_volume_liters, status"),
    ("valves", "valve_id, facility_id, opening_pct, state, status"),
    ("pipes", "pipe_id, facility_id, from_node_id, to_node_id, diameter_mm, length_m, status"),
    ("sensors", "sensor_id, facility_id, component_id, sensor_type, unit, measurement_role, status"),
    ("operating_modes", "operating_mode_id, facility_id, mode_name, effective_from, effective_to, status"),
    ("telemetry", "telemetry_id, sensor_id, timestamp, facility_id, component_id, sensor_type, unit, measurement_role, value, quality_status"),
)


def _load_validated_seed_tables(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    data_path = Path(data_dir)
    validation = validate_dataset(data_path)
    if not validation["valid"]:
        raise ValueError("Refusing to export invalid seed data: " + "; ".join(validation["errors"]))
    return {
        name: pd.read_csv(data_path / f"{name}.csv")
        for name, _ in SEED_TABLES
    }


def _literal(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NULL"
    if isinstance(value, (bool, int)):
        return str(int(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("SQL seed data cannot contain non-finite numbers")
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def export_seed_sql(
    data_dir: str | Path = "data/generated",
    output_path: str | Path = "exports/seed_data.sql",
) -> Path:
    """Write a self-contained SQLite schema and inserts for generated seed data."""
    tables = _load_validated_seed_tables(data_dir)

    statements = ["PRAGMA foreign_keys = ON;", *[schema + ";" for schema in SEED_SCHEMA]]
    for name in ("facilities", "pumps", "tanks", "valves"):
        columns = [column.strip() for column in dict(SEED_TABLES)[name].split(",")]
        for row in tables[name][columns].itertuples(index=False, name=None):
            values = ", ".join(_literal(value) for value in row)
            statements.append(
                f"INSERT INTO {name} ({', '.join(columns)}) VALUES ({values});"
            )

    components = []
    for table_name, id_column, component_type in (
        ("facilities", "facility_id", "facility"),
        ("pumps", "pump_id", "pump"),
        ("tanks", "tank_id", "tank"),
        ("valves", "valve_id", "valve"),
    ):
        for row in tables[table_name][[id_column, "facility_id"]].itertuples(index=False, name=None):
            components.append((row[0], row[1], component_type))
    for component_id, facility_id, component_type in sorted(components):
        statements.append(
            "INSERT INTO components (component_id, facility_id, component_type) "
            f"VALUES ({_literal(component_id)}, {_literal(facility_id)}, {_literal(component_type)});"
        )

    for name in ("pipes", "sensors", "operating_modes", "telemetry"):
        columns = [column.strip() for column in dict(SEED_TABLES)[name].split(",")]
        for row in tables[name][columns].itertuples(index=False, name=None):
            values = ", ".join(_literal(value) for value in row)
            statements.append(
                f"INSERT INTO {name} ({', '.join(columns)}) VALUES ({values});"
            )

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(statements) + "\n", encoding="utf-8")
    return destination


def export_seed_json(
    data_dir: str | Path = "data/generated",
    output_path: str | Path = "exports/seed_data.json",
) -> Path:
    """Write all generated seed tables as a deterministic JSON object."""
    tables = _load_validated_seed_tables(data_dir)
    payload = {
        name: json.loads(frame.to_json(orient="records", double_precision=15))
        for name, frame in tables.items()
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination


def _parse_json_fields(record: dict[str, Any], columns: set[str]) -> dict[str, Any]:
    for column in ("config_json", "output_json", "expected_value"):
        if column in columns and record.get(column) is not None:
            try:
                record[column] = json.loads(record[column])
            except (TypeError, json.JSONDecodeError):
                raise ValueError(f"Database contains invalid JSON in {column}")
    return record


def _write_records(
    records: list[dict[str, Any]],
    csv_path: Path,
    json_path: Path,
    columns: list[str],
) -> None:
    csv_records = [
        {
            key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
            for key, value in record.items()
        }
        for record in records
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(csv_records)
    json_path.write_text(
        json.dumps(records, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def export_simulation_results(
    database_path: str | Path = "industrialpulse.db",
    output_dir: str | Path = "exports",
) -> dict[str, Path]:
    """Export persisted runs and alarms as CSV and JSON without mutating history."""
    db_path = Path(database_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"Simulation database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        existing = {
            row["name"] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing = {"simulation_runs", "alarms"} - existing
        if missing:
            raise ValueError("Database is missing tables: " + ", ".join(sorted(missing)))
        run_rows = conn.execute(
            "SELECT * FROM simulation_runs ORDER BY simulation_run_id"
        ).fetchall()
        alarm_rows = conn.execute(
            "SELECT * FROM alarms ORDER BY alarm_id"
        ).fetchall()
        run_columns = [
            row["name"] for row in conn.execute("PRAGMA table_info(simulation_runs)")
        ]
        alarm_columns = [
            row["name"] for row in conn.execute("PRAGMA table_info(alarms)")
        ]
    finally:
        conn.close()

    runs = [
        _parse_json_fields(dict(row), set(row.keys()))
        for row in run_rows
    ]
    alarms = [
        _parse_json_fields(dict(row), set(row.keys()))
        for row in alarm_rows
    ]
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, records, columns in (
        ("simulation_runs", runs, run_columns),
        ("alarms", alarms, alarm_columns),
    ):
        csv_path = destination / f"{name}.csv"
        json_path = destination / f"{name}.json"
        _write_records(records, csv_path, json_path, columns)
        result[f"{name}_csv"] = csv_path
        result[f"{name}_json"] = json_path
    return result
