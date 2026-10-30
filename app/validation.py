"""Data-integrity validation helpers."""
from pathlib import Path
import pandas as pd
import networkx as nx

def validate_dataset(data_dir="data/generated"):
    root = Path(data_dir)
    errors = []
    facilities = pd.read_csv(root/"facilities.csv")
    pumps = pd.read_csv(root/"pumps.csv")
    tanks = pd.read_csv(root/"tanks.csv")
    valves = pd.read_csv(root/"valves.csv")
    pipes = pd.read_csv(root/"pipes.csv")
    sensors = pd.read_csv(root/"sensors.csv")
    telemetry = pd.read_csv(root/"telemetry.csv")

    for name, df, key in [
        ("facilities", facilities, "facility_id"), ("pumps", pumps, "pump_id"),
        ("tanks", tanks, "tank_id"), ("valves", valves, "valve_id"),
        ("pipes", pipes, "pipe_id"), ("sensors", sensors, "sensor_id"),
        ("telemetry", telemetry, "telemetry_id")
    ]:
        if df[key].isna().any() or df[key].duplicated().any():
            errors.append(f"{name}: missing or duplicate primary key {key}")

    valid_facilities = set(facilities.facility_id)
    for name, df in [("pumps",pumps),("tanks",tanks),("valves",valves),("pipes",pipes),("sensors",sensors)]:
        if not set(df.facility_id).issubset(valid_facilities):
            errors.append(f"{name}: invalid facility foreign key")

    node_ids = set(pumps.pump_id) | set(tanks.tank_id) | set(valves.valve_id) | set(facilities.facility_id)
    for _, row in pipes.iterrows():
        if row.from_node_id not in node_ids or row.to_node_id not in node_ids:
            errors.append(f"pipe {row.pipe_id}: missing endpoint")
    if not set(telemetry.sensor_id).issubset(set(sensors.sensor_id)):
        errors.append("telemetry: invalid sensor foreign key")
    if (tanks.initial_volume_liters > tanks.capacity_liters).any():
        errors.append("tank initial volume exceeds capacity")
    return {"valid": not errors, "errors": errors,
            "counts":{"facilities":len(facilities),"pumps":len(pumps),"tanks":len(tanks),
                      "valves":len(valves),"pipes":len(pipes),"sensors":len(sensors),
                      "telemetry":len(telemetry)}}
