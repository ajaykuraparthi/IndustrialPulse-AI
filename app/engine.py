"""Explainable rule engine for synthetic telemetry."""
from __future__ import annotations

import numpy as np
import pandas as pd

PUMP_PERFORMANCE_RATIO_MIN = 0.75
STUCK_READING_MIN_RUN = 8
PUMP_DEGRADATION_MIN_RUN = 10
PRESSURE_BASELINE_READINGS = 20
PRESSURE_HIGH_RATIO = 1.10
PRESSURE_HIGH_MIN_RUN = 10
FACILITY_FLOW_PROXY_MIN_RUN = 10
FACILITY_FLOW_PROXY_MIN_SENSORS = 3

REQUIRED_TELEMETRY_COLUMNS = {
    "sensor_id", "timestamp", "facility_id", "component_id", "sensor_type",
    "measurement_role", "value",
}


def _true_runs(mask: pd.Series) -> list[tuple[int, int]]:
    values = mask.fillna(False).to_numpy(dtype=bool)
    edges = np.diff(np.r_[False, values, False].astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1) - 1
    return list(zip(starts.tolist(), ends.tolist()))


def _time_fields(group: pd.DataFrame, start: int, end: int) -> dict:
    start_time = group["timestamp"].iloc[start]
    end_time = group["timestamp"].iloc[end]
    return {
        "timestamp": start_time.isoformat(),
        "window_start": start_time.isoformat(),
        "window_end": end_time.isoformat(),
    }


def _prepare_telemetry(telemetry: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_TELEMETRY_COLUMNS - set(telemetry.columns)
    if missing:
        raise ValueError(
            "Telemetry is missing required columns: " + ", ".join(sorted(missing))
        )

    timestamps = pd.to_datetime(telemetry["timestamp"], utc=True, errors="coerce")
    values = pd.to_numeric(telemetry["value"], errors="coerce")
    invalid_timestamps = timestamps.isna()
    invalid_values = values.isna() | ~np.isfinite(values)
    missing_metadata = telemetry[
        ["sensor_id", "facility_id", "component_id", "sensor_type", "measurement_role"]
    ].isna().any(axis=1)
    invalid_quality = pd.Series(False, index=telemetry.index)
    if "quality_status" in telemetry.columns:
        invalid_quality = ~telemetry["quality_status"].isin(("good", "suspect"))
    invalid_rows = invalid_timestamps | invalid_values | missing_metadata | invalid_quality
    if invalid_rows.any():
        examples = telemetry.index[invalid_rows].tolist()[:5]
        raise ValueError(
            "Telemetry contains malformed rows: "
            f"{int(invalid_timestamps.sum())} invalid timestamps, "
            f"{int(invalid_values.sum())} invalid/non-finite values, "
            f"{int(missing_metadata.sum())} missing identifiers/metadata, "
            f"{int(invalid_quality.sum())} invalid quality statuses; "
            f"example row indexes: {examples}"
        )

    order = np.argsort(timestamps.array.asi8, kind="stable")
    prepared = telemetry.iloc[order].copy()
    prepared["timestamp"] = timestamps.iloc[order].array
    prepared["value"] = values.iloc[order].to_numpy(dtype=float)
    return prepared


def detect_anomalies(telemetry: pd.DataFrame, pumps: pd.DataFrame) -> list[dict]:
    """Return explainable alarms using telemetry features, not ground-truth labels."""
    if telemetry.empty:
        return []

    work = _prepare_telemetry(telemetry)
    alarms: list[dict] = []

    # Sensor quality checks; sensor_id identifies the instrument, component_id its target.
    for sensor_id, group in work.groupby("sensor_id", sort=True):
        vals = group["value"]
        sensor = group.iloc[0]
        component_id = sensor["component_id"]
        stype = sensor["sensor_type"]

        same_as_previous = vals.eq(vals.shift())
        run_ids = (~same_as_previous).cumsum()
        run_lengths = vals.groupby(run_ids).transform("size")
        stuck_mask = run_lengths >= STUCK_READING_MIN_RUN

        for start, end in _true_runs(stuck_mask):
            alarms.append({
                "component_id": component_id,
                "sensor_id": sensor_id,
                "alarm_type": "sensor_fault",
                "severity": "medium",
                "rule_id": "SENSOR_STUCK_VALUE",
                "observed_value": float(vals.iloc[start]),
                "expected_value": "Readings should vary when operating conditions change",
                **_time_fields(group, start, end),
                "explanation": (
                    f"Sensor {sensor_id} has at least "
                    f"{STUCK_READING_MIN_RUN} consecutive identical readings."
                )
            })

        negative = vals < 0
        if stype in ("flow", "pressure", "level") and negative.any():
            positions = np.flatnonzero(negative.to_numpy())
            start, end = int(positions[0]), int(positions[-1])
            alarms.append({
                "component_id": component_id,
                "sensor_id": sensor_id,
                "alarm_type": "sensor_fault",
                "severity": "high",
                "rule_id": "NEGATIVE_PHYSICAL_READING",
                "observed_value": float(vals.min()),
                "expected_value": ">= 0",
                **_time_fields(group, start, end),
                "explanation": (
                    f"Sensor {sensor_id} contains a negative {stype} reading."
                )
            })

    # Freeze a past-only reference before screening so a sustained event cannot
    # raise its own baseline. This is an indicator, not proof of a blockage.
    pressure = work[work["sensor_type"] == "pressure"]
    if "quality_status" in pressure.columns:
        pressure = pressure[pressure["quality_status"] == "good"]
    for sensor_id, group in pressure.groupby("sensor_id", sort=True):
        values = group["value"]
        if len(values) <= PRESSURE_BASELINE_READINGS:
            continue
        baseline = float(values.iloc[:PRESSURE_BASELINE_READINGS].median())
        if baseline <= 0:
            continue
        high = pd.Series(False, index=values.index)
        high.iloc[PRESSURE_BASELINE_READINGS:] = (
            values.iloc[PRESSURE_BASELINE_READINGS:]
            > baseline * PRESSURE_HIGH_RATIO
        )
        for start, end in _true_runs(high):
            if end - start + 1 < PRESSURE_HIGH_MIN_RUN:
                continue
            alarms.append({
                "component_id": group.iloc[0]["component_id"],
                "sensor_id": sensor_id,
                "alarm_type": "pressure_anomaly",
                "severity": "medium",
                "rule_id": "SUSTAINED_HIGH_PRESSURE",
                "observed_value": float(values.iloc[start:end + 1].median()),
                "expected_value": baseline,
                **_time_fields(group, start, end),
                "explanation": (
                    f"Sensor {sensor_id} has sustained pressure readings above "
                    f"{PRESSURE_HIGH_RATIO:.0%} of its initial "
                    f"{PRESSURE_BASELINE_READINGS}-reading baseline ({baseline:.2f} kPa). "
                    "Investigate possible blockage or other abnormal operating conditions."
                )
            })

    pump_columns = {"pump_id", "nominal_flow_lps"}
    if not pumps.empty and not pump_columns.issubset(pumps.columns):
        raise ValueError("Pump data requires pump_id and nominal_flow_lps columns")
    nominal_by_pump: dict[str, float] = {}
    if not pumps.empty:
        nominal_values = pd.to_numeric(pumps["nominal_flow_lps"], errors="coerce")
        invalid_nominal = nominal_values.isna() | ~np.isfinite(nominal_values) | (nominal_values <= 0)
        if invalid_nominal.any() or pumps["pump_id"].isna().any():
            raise ValueError("Pump data contains missing IDs or invalid nominal_flow_lps values")
        nominal_by_pump = dict(zip(pumps["pump_id"], nominal_values.astype(float)))

    flow = work[work["sensor_type"] == "flow"]
    if "quality_status" in flow.columns:
        flow = flow[flow["quality_status"] == "good"]
    pump_facility = dict(zip(flow["component_id"], flow["facility_id"]))
    # Nominal pump flow is an independent reference, so a degradation event
    # cannot pull its own baseline down as the event continues.
    for component_id, group in flow.groupby("component_id", sort=True):
        expected = nominal_by_pump.get(component_id)
        if expected is None:
            continue
        for sensor_id, sensor_group in group.groupby("sensor_id", sort=True):
            low = sensor_group["value"] < expected * PUMP_PERFORMANCE_RATIO_MIN
            for start, end in _true_runs(low):
                if end - start + 1 < PUMP_DEGRADATION_MIN_RUN:
                    continue
                alarms.append({
                    "component_id": component_id,
                    "sensor_id": sensor_id,
                    "alarm_type": "pump_degradation",
                    "severity": "high",
                    "rule_id": "PUMP_PERFORMANCE_RATIO",
                    "observed_value": float(sensor_group["value"].iloc[start:end + 1].median()),
                    "expected_value": expected,
                    **_time_fields(sensor_group, start, end),
                    "explanation": (
                        f"Sensor {sensor_id} recorded at least {PUMP_DEGRADATION_MIN_RUN} "
                        f"consecutive flows below {PUMP_PERFORMANCE_RATIO_MIN:.0%} "
                        f"of pump nominal flow ({expected:.2f} L/s)."
                    )
                })

    # The generator has no paired hydraulic inlet/outlet balance. Use only a
    # facility-level, multi-pump low-flow proxy and never claim it proves a leak.
    facility_flow = flow[flow["component_id"].isin(nominal_by_pump)].copy()
    facility_flow["_nominal_ratio"] = facility_flow["value"] / facility_flow[
        "component_id"
    ].map(nominal_by_pump)
    for facility_id, facility_group in facility_flow.groupby("facility_id", sort=True):
        role_runs: dict[str, list[dict]] = {}
        for role, role_group in facility_group[
            facility_group["measurement_role"].isin(("inlet", "outlet"))
        ].groupby("measurement_role", sort=True):
            low = role_group["_nominal_ratio"] < PUMP_PERFORMANCE_RATIO_MIN
            for start, end in _true_runs(low):
                if end - start + 1 < FACILITY_FLOW_PROXY_MIN_RUN:
                    continue
                run = role_group.iloc[start:end + 1]
                role_runs.setdefault(role, []).append({
                    "start": run["timestamp"].iloc[0],
                    "end": run["timestamp"].iloc[-1],
                    "rows": run,
                })

        roles = sorted(role_runs)
        if len(roles) >= 2:
            candidates = []
            for first in role_runs[roles[0]]:
                for second in role_runs[roles[1]]:
                    if max(first["start"], second["start"]) <= min(first["end"], second["end"]):
                        candidates.append((first, second))
        else:
            candidates = [(run,) for runs in role_runs.values() for run in runs]

        for candidate in candidates:
            event_rows = pd.concat([run["rows"] for run in candidate])
            sensor_ids = sorted(event_rows["sensor_id"].unique().tolist())
            if len(sensor_ids) < FACILITY_FLOW_PROXY_MIN_SENSORS:
                continue
            event_rows = event_rows.sort_values("timestamp", kind="stable")
            alarms.append({
                "component_id": facility_id,
                "sensor_ids": sensor_ids,
                "alarm_type": "possible_leak",
                "severity": "medium",
                "rule_id": "FACILITY_FLOW_DEPRESSION_PROXY",
                "observed_value": float(event_rows["_nominal_ratio"].median()),
                "expected_value": PUMP_PERFORMANCE_RATIO_MIN,
                **_time_fields(event_rows, 0, len(event_rows) - 1),
                "explanation": (
                    f"Normalized flow fell below {PUMP_PERFORMANCE_RATIO_MIN:.0%} "
                    f"of nominal across {len(sensor_ids)} facility pump sensors "
                    "in the available flow roles. This is a facility-level low-flow "
                    "proxy, not evidence that a leak is present."
                )
            })

    # A simultaneous facility-level drop is not enough to attribute separate
    # pump failures. Keep the aggregate proxy and its sensor list instead.
    facility_proxies = [
        alarm for alarm in alarms
        if alarm["rule_id"] == "FACILITY_FLOW_DEPRESSION_PROXY"
    ]
    alarms = [
        alarm for alarm in alarms
        if not (
            alarm["alarm_type"] == "pump_degradation"
            and any(
                pump_facility.get(alarm["component_id"]) == proxy["component_id"]
                and pd.Timestamp(alarm["window_start"]) <= pd.Timestamp(proxy["window_end"])
                and pd.Timestamp(alarm["window_end"]) >= pd.Timestamp(proxy["window_start"])
                for proxy in facility_proxies
            )
        )
    ]

    return alarms