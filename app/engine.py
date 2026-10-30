"""Explainable rule engine for synthetic telemetry."""
from __future__ import annotations
from typing import Iterable
import pandas as pd

FLOW_RESIDUAL_TOLERANCE_LPS = 8.0
PUMP_PERFORMANCE_RATIO_MIN = 0.75
STUCK_READING_MIN_RUN = 8

def detect_anomalies(telemetry: pd.DataFrame, pumps: pd.DataFrame) -> list[dict]:
    """Return alarms from telemetry features only; never accepts ground-truth labels."""
    alarms: list[dict] = []
    if telemetry.empty:
        return alarms

    # Sensor quality checks: long constant runs, impossible negative physical readings.
    for sensor_id, group in telemetry.sort_values("timestamp").groupby("sensor_id"):
        vals = group["value"].astype(float)
        if len(vals) >= STUCK_READING_MIN_RUN and vals.nunique() <= 1:
            alarms.append({
                "component_id": group.iloc[0]["component_id"],
                "alarm_type": "sensor_fault",
                "severity": "medium",
                "rule_id": "SENSOR_STUCK_VALUE",
                "observed_value": float(vals.iloc[-1]),
                "expected_value": None,
                "explanation": f"Sensor {sensor_id} returned a constant value across {len(vals)} samples."
            })
        stype = group.iloc[0]["sensor_type"]
        if stype in ("flow", "pressure", "level") and (vals < 0).any():
            alarms.append({
                "component_id": group.iloc[0]["component_id"],
                "alarm_type": "sensor_fault",
                "severity": "high",
                "rule_id": "NEGATIVE_PHYSICAL_READING",
                "observed_value": float(vals.min()),
                "expected_value": ">= 0",
                "explanation": f"Sensor {sensor_id} contains a negative {stype} reading."
            })

    # Pump degradation: compare observed pump flow to its nominal rated flow.
    flow = telemetry[telemetry["sensor_type"] == "flow"]
    for _, pump in pumps.iterrows():
        rows = flow[flow["component_id"] == pump["pump_id"]]
        if rows.empty:
            continue
        observed = float(rows["value"].median())
        expected = float(pump["nominal_flow_lps"])
        ratio = observed / expected if expected > 0 else 1.0
        if ratio < PUMP_PERFORMANCE_RATIO_MIN:
            alarms.append({
                "component_id": pump["pump_id"],
                "alarm_type": "pump_degradation",
                "severity": "high",
                "rule_id": "PUMP_PERFORMANCE_RATIO",
                "observed_value": observed,
                "expected_value": expected,
                "explanation": f"Median flow is {ratio:.2f} of nominal flow; threshold is {PUMP_PERFORMANCE_RATIO_MIN:.2f}."
            })

    # A facility-wide flow residual is a screening indicator, not proof of a leak.
    # Use grouped readings only when both inlet/outlet tagged sensors are present.
    for facility_id, group in telemetry.groupby("facility_id"):
        inlet = group[group["measurement_role"] == "inlet"]["value"].mean()
        outlet = group[group["measurement_role"] == "outlet"]["value"].mean()
        if pd.notna(inlet) and pd.notna(outlet):
            residual = float(inlet - outlet)
            if residual > FLOW_RESIDUAL_TOLERANCE_LPS:
                alarms.append({
                    "component_id": facility_id,
                    "alarm_type": "possible_leak",
                    "severity": "medium",
                    "rule_id": "FLOW_BALANCE_RESIDUAL",
                    "observed_value": residual,
                    "expected_value": 0.0,
                    "explanation": f"Inlet/outlet mean flow residual is {residual:.2f} L/s, above tolerance."
                })
    return alarms
