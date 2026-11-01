"""Dataset and traceability validation helpers."""
from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

FLOW_BALANCE_TOLERANCE_LPS = 8.0


def validate_flow_balance(
    record: Mapping[str, Any],
    tolerance_lps: float = FLOW_BALANCE_TOLERANCE_LPS,
) -> dict[str, Any]:
    """Derive flow residual from source flows and tank-volume change."""
    required = {
        "inlet_flows_lps",
        "outlet_flows_lps",
        "tank_volume_change_liters",
        "interval_seconds",
    }
    missing = required - set(record)
    if missing:
        raise ValueError("Flow balance is missing fields: " + ", ".join(sorted(missing)))
    try:
        tolerance = float(tolerance_lps)
    except (TypeError, ValueError) as error:
        raise ValueError("Flow-balance tolerance must be numeric") from error
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Flow-balance tolerance must be finite and non-negative")

    raw_inlets = record["inlet_flows_lps"]
    raw_outlets = record["outlet_flows_lps"]
    if not isinstance(raw_inlets, (list, tuple)) or not isinstance(
        raw_outlets, (list, tuple)
    ):
        raise ValueError("Flow measurements must be lists")
    try:
        inlets = [float(value) for value in raw_inlets]
        outlets = [float(value) for value in raw_outlets]
        volume_change = float(record["tank_volume_change_liters"])
        interval = float(record["interval_seconds"])
    except (TypeError, ValueError) as error:
        raise ValueError("Flow-balance source measurements must be numeric") from error
    measurements = inlets + outlets + [volume_change, interval]
    if (not inlets or not outlets or not all(math.isfinite(value) for value in measurements)
            or any(value < 0 for value in inlets + outlets) or interval <= 0):
        raise ValueError("Flow balance requires finite flows and a positive interval")

    storage_rate_lps = volume_change / interval
    residual_lps = math.fsum(inlets) - math.fsum(outlets) - storage_rate_lps
    if not math.isfinite(residual_lps):
        raise ValueError("Flow-balance residual must be finite")
    return {
        "valid": abs(residual_lps) <= tolerance,
        "residual_lps": residual_lps,
        "storage_rate_lps": storage_rate_lps,
        "tolerance_lps": tolerance,
    }


def validate_simulation_record(record: Mapping[str, Any]) -> None:
    """Reject simulation results that cannot be traced to complete inputs."""
    required = {
        "simulation_run_id", "facility_id", "pump_id", "config_json",
        "seed", "status", "output_json",
    }
    missing = required - set(record)
    if missing:
        raise ValueError("simulation_missing_fields: " + ", ".join(sorted(missing)))

    config_value = record["config_json"]
    output_value = record["output_json"]
    if isinstance(config_value, str):
        try:
            config_value = json.loads(config_value)
        except json.JSONDecodeError as error:
            raise ValueError("simulation_invalid_configuration: config_json is not valid JSON") from error
    if not isinstance(config_value, Mapping) or not config_value:
        raise ValueError("simulation_missing_configuration: config_json must be a non-empty object")
    if isinstance(output_value, str):
        try:
            output_value = json.loads(output_value)
        except json.JSONDecodeError as error:
            raise ValueError("simulation_invalid_output: output_json is not valid JSON") from error
    if not isinstance(output_value, Mapping) or not output_value:
        raise ValueError("simulation_missing_output: output_json must be a non-empty object")
    for field in ("predicted_flow_lps", "predicted_head_kpa"):
        try:
            output_number = float(output_value[field])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"simulation_invalid_output: {field} is required and numeric") from error
        if not math.isfinite(output_number) or output_number < 0:
            raise ValueError(f"simulation_invalid_output: {field} must be finite and non-negative")

    assumptions = config_value.get("assumptions")
    if not isinstance(assumptions, str) or not assumptions.strip():
        raise ValueError("simulation_missing_assumptions: configuration must document assumptions")
    model_version = config_value.get("model_version")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("simulation_missing_model_version")
    try:
        speed_pct = float(config_value["speed_pct"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("simulation_invalid_speed: configuration speed_pct is required") from error
    if not math.isfinite(speed_pct) or not 10 <= speed_pct <= 120:
        raise ValueError("simulation_invalid_speed: speed_pct must be between 10 and 120")
    if config_value.get("simulation_run_id") != record["simulation_run_id"]:
        raise ValueError("simulation_run_identity_mismatch: configuration run ID does not match record")
    if config_value.get("pump_id") != record["pump_id"]:
        raise ValueError("simulation_pump_mismatch: configuration pump does not match record")
    if config_value.get("seed") != record["seed"]:
        raise ValueError("simulation_seed_mismatch: configuration seed does not match record")
    if record["status"] not in {"completed", "failed"}:
        raise ValueError("simulation_invalid_status: status must be completed or failed")
    configuration_hash = record.get("configuration_hash")
    if configuration_hash is not None:
        canonical = json.dumps(config_value, sort_keys=True)
        expected_hash = hashlib.sha256(canonical.encode()).hexdigest()
        if configuration_hash != expected_hash:
            raise ValueError("simulation_configuration_hash_mismatch")


def validate_dataset(data_dir: str | Path = "data/generated") -> dict[str, Any]:
    """Validate generated tables and return observed counts and check results."""
    root = Path(data_dir)
    files = {
        "facilities": "facilities.csv",
        "pumps": "pumps.csv",
        "tanks": "tanks.csv",
        "valves": "valves.csv",
        "pipes": "pipes.csv",
        "sensors": "sensors.csv",
        "operating_modes": "operating_modes.csv",
        "telemetry": "telemetry.csv",
    }
    frames = {name: pd.read_csv(root / filename) for name, filename in files.items()}
    errors: list[str] = []
    counts = {name: len(frame) for name, frame in frames.items()}
    for name, expected in {
        "facilities": 3,
        "pumps": 20,
        "tanks": 30,
        "valves": 60,
    }.items():
        if counts[name] != expected:
            errors.append(f"{name}: expected {expected} records, found {counts[name]}")

    primary_keys = {
        "facilities": "facility_id",
        "pumps": "pump_id",
        "tanks": "tank_id",
        "valves": "valve_id",
        "pipes": "pipe_id",
        "sensors": "sensor_id",
        "operating_modes": "operating_mode_id",
        "telemetry": "telemetry_id",
    }
    for name, key in primary_keys.items():
        frame = frames[name]
        if key not in frame:
            errors.append(f"{name}: missing primary-key column {key}")
        elif frame[key].isna().any() or frame[key].astype(str).str.strip().eq("").any():
            errors.append(f"{name}: missing primary key {key}")
        elif frame[key].duplicated().any():
            errors.append(f"{name}: duplicate primary key {key}")

    def has_columns(name: str, *columns: str) -> bool:
        missing = set(columns) - set(frames[name].columns)
        if missing:
            errors.append(f"{name}: missing columns {', '.join(sorted(missing))}")
            return False
        return True

    facility_ids = set(frames["facilities"].get("facility_id", pd.Series(dtype=str)).dropna())
    component_facility: dict[str, Any] = {}
    component_tables = ("pumps", "tanks", "valves")
    for name in (*component_tables, "pipes", "sensors", "operating_modes"):
        if has_columns(name, "facility_id"):
            invalid = set(frames[name]["facility_id"].dropna()) - facility_ids
            if invalid:
                errors.append(f"{name}: invalid facility foreign key")
    for name, id_column in (
        ("pumps", "pump_id"), ("tanks", "tank_id"), ("valves", "valve_id")
    ):
        if has_columns(name, id_column, "facility_id"):
            for component_id, facility_id in zip(
                frames[name][id_column], frames[name]["facility_id"]
            ):
                if pd.notna(component_id):
                    component_facility[str(component_id)] = facility_id
    topology_ids = [
        component_id
        for name, id_column in (
            ("pumps", "pump_id"), ("tanks", "tank_id"), ("valves", "valve_id")
        )
        if id_column in frames[name]
        for component_id in frames[name][id_column].dropna().astype(str)
    ]
    if len(topology_ids) != len(set(topology_ids)):
        errors.append("topology: component IDs must be globally unique")

    facilities = frames["facilities"]
    if has_columns("facilities", "status") and not facilities["status"].isin(
        ("active", "inactive")
    ).all():
        errors.append("facilities: status must be active or inactive")
    for name in ("pumps", "tanks", "valves", "pipes", "sensors"):
        if has_columns(name, "status") and not frames[name]["status"].isin(
            ("active", "inactive")
        ).all():
            errors.append(f"{name}: status must be active or inactive")

    numeric_positive = {
        "pumps": ("nominal_flow_lps", "shutoff_head_kpa", "curve_k"),
        "tanks": ("capacity_liters",),
        "pipes": ("diameter_mm", "length_m"),
    }
    for name, columns in numeric_positive.items():
        if has_columns(name, *columns):
            for column in columns:
                values = pd.to_numeric(frames[name][column], errors="coerce")
                if (values.isna().any() or not values.map(math.isfinite).all()
                        or (~(values > 0)).any()):
                    errors.append(f"{name}: {column} must be finite and greater than zero")

    tanks = frames["tanks"]
    if has_columns("tanks", "tank_id", "capacity_liters", "initial_volume_liters"):
        capacity = pd.to_numeric(tanks["capacity_liters"], errors="coerce")
        initial = pd.to_numeric(tanks["initial_volume_liters"], errors="coerce")
        finite = capacity.map(math.isfinite) & initial.map(math.isfinite)
        if (capacity.isna() | initial.isna() | ~finite | (initial < 0) | (initial > capacity)).any():
            errors.append("tanks: initial volume exceeds capacity or is invalid")

    valves = frames["valves"]
    if has_columns("valves", "opening_pct", "state"):
        opening = pd.to_numeric(valves["opening_pct"], errors="coerce")
        if (opening.isna() | (opening < 0) | (opening > 100)).any():
            errors.append("valves: opening_pct must be between 0 and 100")
        if not valves["state"].isin(("open", "closed")).all():
            errors.append("valves: state must be open or closed")

    pipes = frames["pipes"]
    if has_columns("pipes", "pipe_id", "facility_id", "from_node_id", "to_node_id"):
        node_ids = set(component_facility)
        for _, row in pipes.iterrows():
            start = str(row["from_node_id"])
            end = str(row["to_node_id"])
            if start not in node_ids or end not in node_ids:
                errors.append(f"pipe {row['pipe_id']}: missing topology node")
                continue
            if (component_facility[start] != component_facility[end]
                    or component_facility[start] != row["facility_id"]):
                errors.append(f"pipe {row['pipe_id']}: endpoints must belong to pipe facility")
            if start == end:
                errors.append(f"pipe {row['pipe_id']}: endpoints must be distinct")

    sensors = frames["sensors"]
    sensor_columns = ("sensor_id", "facility_id", "component_id", "sensor_type", "unit",
                      "measurement_role")
    if has_columns("sensors", *sensor_columns):
        if sensors["sensor_id"].duplicated().any():
            errors.append("sensors: duplicate sensor_id")
        allowed = {
            "flow": ("L/s", {"inlet", "outlet"}),
            "pressure": ("kPa", {"pressure"}),
            "level": ("L", {"level"}),
        }
        for _, row in sensors.iterrows():
            spec = allowed.get(row["sensor_type"])
            if spec is None or row["unit"] != spec[0] or row["measurement_role"] not in spec[1]:
                errors.append(f"sensor {row['sensor_id']}: invalid type, unit, or measurement role")
            target_facility = row["facility_id"] if row["component_id"] == row["facility_id"] else component_facility.get(str(row["component_id"]))
            if target_facility != row["facility_id"]:
                errors.append(f"sensor {row['sensor_id']}: component/facility relationship is invalid")

    modes = frames["operating_modes"]
    if has_columns("operating_modes", "effective_from", "effective_to", "status"):
        start = pd.to_datetime(modes["effective_from"], utc=True, errors="coerce")
        end = pd.to_datetime(modes["effective_to"], utc=True, errors="coerce")
        if start.isna().any() or (end.notna() & (end < start)).any():
            errors.append("operating_modes: invalid effective date range")
        if not modes["status"].isin(("active", "inactive")).all():
            errors.append("operating_modes: status must be active or inactive")
        for facility_id, group in modes.assign(_start=start, _end=end).groupby("facility_id"):
            active = group[group["status"] == "active"].sort_values("_start")
            prior_end = None
            for _, row in active.iterrows():
                if prior_end is not None and (pd.isna(prior_end) or row["_start"] <= prior_end):
                    errors.append(f"operating_modes: overlapping active modes for {facility_id}")
                    break
                prior_end = row["_end"]

    telemetry = frames["telemetry"]
    telemetry_columns = (
        "telemetry_id", "sensor_id", "timestamp", "facility_id", "component_id",
        "sensor_type", "unit", "measurement_role", "value", "quality_status",
    )
    if has_columns("telemetry", *telemetry_columns):
        sensor_ids = set(sensors.get("sensor_id", pd.Series(dtype=str)).dropna())
        if not set(telemetry["sensor_id"].dropna()).issubset(sensor_ids):
            errors.append("telemetry: invalid sensor foreign key")
        timestamps = pd.to_datetime(telemetry["timestamp"], utc=True, errors="coerce")
        values = pd.to_numeric(telemetry["value"], errors="coerce")
        if timestamps.isna().any():
            errors.append("telemetry: invalid timestamp")
        else:
            normalized_keys = pd.DataFrame({
                "sensor_id": telemetry["sensor_id"],
                "timestamp": timestamps,
            })
            if normalized_keys.duplicated().any():
                errors.append("telemetry: duplicate sensor/timestamp record")
        if values.isna().any() or not values.map(math.isfinite).all():
            errors.append("telemetry: value must be finite numeric")
        if not telemetry["quality_status"].isin(("good", "suspect")).all():
            errors.append("telemetry: quality_status must be good or suspect")
        if not telemetry["sensor_type"].isin(("flow", "pressure", "level")).all():
            errors.append("telemetry: unsupported sensor_type")
        if (values < 0).any():
            errors.append("telemetry: physical readings must be non-negative")
        if len(telemetry) and len(sensors):
            sensor_lookup = sensors.set_index("sensor_id")
            for column in ("facility_id", "component_id", "sensor_type", "unit", "measurement_role"):
                expected = telemetry["sensor_id"].map(sensor_lookup[column])
                if (expected.isna() | expected.ne(telemetry[column])).any():
                    errors.append(f"telemetry: {column} does not match sensor metadata")
                    break
            level_rows = telemetry[telemetry["sensor_type"] == "level"]
            tank_capacity = tanks.set_index("tank_id")["capacity_liters"] if "tank_id" in tanks else pd.Series(dtype=float)
            levels = pd.to_numeric(level_rows["value"], errors="coerce")
            capacities = pd.to_numeric(level_rows["component_id"].map(tank_capacity), errors="coerce")
            if (capacities.isna() | (levels < 0) | (levels > capacities)).any():
                errors.append("telemetry: tank level exceeds capacity or references an invalid tank")

    balance_count = 0
    balance_valid = True
    balance_intervals: list[dict[str, Any]] = []
    balance_path = root / "flow_balances.csv"
    if balance_path.is_file():
        balances = pd.read_csv(balance_path)
        pumps = frames["pumps"]
        required = {
            "balance_id", "facility_id", "interval_start", "interval_seconds",
            "measurement_basis", "inlet_flows_lps", "outlet_flows_lps",
            "tank_volume_change_liters",
        }
        if not required.issubset(balances.columns):
            errors.append("flow_balances: missing required balance source columns")
            balance_valid = False
        else:
            balance_count = len(balances)
            if balances["balance_id"].isna().any() or balances["balance_id"].duplicated().any():
                errors.append("flow_balances: balance_id must be present and unique")
                balance_valid = False
            pump_nominals = (
                pumps.set_index("pump_id")["nominal_flow_lps"]
                if {"pump_id", "nominal_flow_lps"}.issubset(pumps.columns)
                else pd.Series(dtype=float)
            )
            for _, row in balances.iterrows():
                interval_id = str(row["balance_id"])
                interval_detail: dict[str, Any] = {
                    "balance_id": interval_id,
                    "facility_id": str(row["facility_id"]),
                    "measurement_basis": str(row["measurement_basis"]),
                    "valid": False,
                }
                if row["facility_id"] not in facility_ids:
                    errors.append("flow_balances: invalid facility foreign key")
                    balance_valid = False
                    balance_intervals.append(interval_detail)
                    continue
                if row["measurement_basis"] not in {"measured", "modeled"}:
                    errors.append(
                        f"flow_balances: {interval_id} has invalid measurement_basis"
                    )
                    balance_valid = False
                    balance_intervals.append(interval_detail)
                    continue
                interval_start = pd.to_datetime(
                    row["interval_start"], utc=True, errors="coerce"
                )
                if pd.isna(interval_start):
                    errors.append(
                        f"flow_balances: {interval_id} has invalid interval_start"
                    )
                    balance_valid = False
                    balance_intervals.append(interval_detail)
                    continue
                try:
                    inlet_flows = json.loads(row["inlet_flows_lps"])
                    outlet_flows = json.loads(row["outlet_flows_lps"])
                    source_record = {
                        "inlet_flows_lps": inlet_flows,
                        "outlet_flows_lps": outlet_flows,
                        "tank_volume_change_liters": row["tank_volume_change_liters"],
                        "interval_seconds": row["interval_seconds"],
                    }
                    result = validate_flow_balance(source_record)
                except (TypeError, ValueError) as error:
                    errors.append(f"flow_balances: invalid source data: {error}")
                    balance_valid = False
                    balance_intervals.append(interval_detail)
                    continue
                interval_seconds = float(row["interval_seconds"])
                interval_detail.update({
                    "interval_start": interval_start.isoformat(),
                    "interval_end": (
                        interval_start + pd.to_timedelta(interval_seconds, unit="s")
                    ).isoformat(),
                    "residual_lps": result["residual_lps"],
                    "tolerance_lps": result["tolerance_lps"],
                    "valid": result["valid"],
                })

                if row["measurement_basis"] == "modeled":
                    try:
                        if row["model_name"] != "steady_state_bottlenecked_nominal_capacity":
                            raise ValueError("unsupported model_name")
                        demand_factor = float(row["demand_factor"])
                        capacities_by_role = json.loads(
                            row["source_pump_capacities_json"]
                        )
                        if not math.isfinite(demand_factor) or not 0 < demand_factor <= 1:
                            raise ValueError("demand_factor must be in (0, 1]")
                        if not isinstance(capacities_by_role, dict):
                            raise ValueError("pump capacity sources must be an object")

                        facility_flow_sensors = sensors[
                            (sensors["facility_id"] == row["facility_id"])
                            & (sensors["sensor_type"] == "flow")
                        ]
                        expected_flows: dict[str, list[float]] = {}
                        for role in ("inlet", "outlet"):
                            sources = capacities_by_role.get(role)
                            expected_pump_ids = set(
                                facility_flow_sensors.loc[
                                    facility_flow_sensors["measurement_role"] == role,
                                    "component_id",
                                ]
                            )
                            if not isinstance(sources, list) or not sources:
                                raise ValueError(f"{role} pump capacities are missing")
                            source_ids = [source["pump_id"] for source in sources]
                            if len(source_ids) != len(set(source_ids)) or set(source_ids) != expected_pump_ids:
                                raise ValueError(f"{role} pump source references are invalid")
                            source_capacities = []
                            for source in sources:
                                capacity = float(source["nominal_flow_lps"])
                                master_capacity = float(pump_nominals[source["pump_id"]])
                                if (not math.isfinite(capacity) or capacity <= 0
                                        or not math.isclose(capacity, master_capacity, abs_tol=1e-9)):
                                    raise ValueError("pump capacity does not match master data")
                                source_capacities.append(capacity)
                            expected_flows[role] = source_capacities

                        role_totals = {
                            role: math.fsum(capacities)
                            for role, capacities in expected_flows.items()
                        }
                        throughput = min(role_totals.values()) * demand_factor
                        for role, observed_flows in (
                            ("inlet", inlet_flows), ("outlet", outlet_flows)
                        ):
                            expected_values = [
                                round(throughput * capacity / role_totals[role], 6)
                                for capacity in expected_flows[role]
                            ]
                            if (not isinstance(observed_flows, list)
                                    or len(observed_flows) != len(expected_values)
                                    or any(
                                        not math.isclose(float(actual), expected, abs_tol=1e-6)
                                        for actual, expected in zip(observed_flows, expected_values)
                                    )):
                                raise ValueError(f"{role} flows do not match modeled pump inputs")
                        if float(row["tank_volume_change_liters"]) != 0:
                            raise ValueError("steady-state modeled storage change must be zero")
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                        errors.append(
                            f"flow_balances: invalid modeled source for {interval_id}: {error}"
                        )
                        balance_valid = False
                        interval_detail["valid"] = False
                        balance_intervals.append(interval_detail)
                        continue

                if not result["valid"]:
                    errors.append(
                        f"flow_balances: {row['facility_id']} residual "
                        f"{result['residual_lps']:.3f} L/s exceeds "
                        f"{result['tolerance_lps']:.3f} L/s tolerance"
                    )
                    balance_valid = False
                balance_intervals.append(interval_detail)

    return {
        "valid": not errors,
        "errors": errors,
        "counts": counts,
        "checks": {
            "flow_balance_records_checked": balance_count,
            "flow_balance_tolerance_lps": FLOW_BALANCE_TOLERANCE_LPS,
            "flow_balances_valid": balance_valid,
            "flow_balance_intervals": balance_intervals,
        },
    }
