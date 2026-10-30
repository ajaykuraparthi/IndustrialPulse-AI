"""Deterministic synthetic data generation for IndustrialPulse AI."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import networkx as nx

ID = lambda prefix, n, width=3: f"{prefix}-{n:0{width}d}"

def generate_dataset(output_dir="data/generated", seed=20261022, telemetry_count=100000):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    facilities = pd.DataFrame([
        {"facility_id": ID("FAC", i), "name": f"Facility {i}", "status": "active"}
        for i in range(1, 4)
    ])
    pumps = []
    for i in range(1, 21):
        pumps.append({"pump_id": ID("PUMP", i), "facility_id": ID("FAC", ((i-1)%3)+1),
                      "nominal_flow_lps": round(float(rng.uniform(35, 100)), 3),
                      "shutoff_head_kpa": round(float(rng.uniform(250, 500)), 2),
                      "curve_k": round(float(rng.uniform(.01, .05)), 5),
                      "status": "active"})
    pumps = pd.DataFrame(pumps)
    tanks = pd.DataFrame([
        {"tank_id": ID("TANK", i), "facility_id": ID("FAC", ((i-1)%3)+1),
         "capacity_liters": int(rng.integers(12000, 60000)),
         "initial_volume_liters": int(rng.integers(3000, 10000)), "status": "active"}
        for i in range(1, 31)
    ])
    valves = pd.DataFrame([
        {"valve_id": ID("VALVE", i), "facility_id": ID("FAC", ((i-1)%3)+1),
         "opening_pct": int(rng.integers(45, 101)), "state": "open", "status": "active"}
        for i in range(1, 61)
    ])

    # Nodes are components; each baseline pipe connects two valid nodes within a facility.
    nodes = []
    for _, row in pumps.iterrows():
        nodes.append((row["pump_id"], row["facility_id"]))
    for _, row in tanks.iterrows():
        nodes.append((row["tank_id"], row["facility_id"]))
    for _, row in valves.iterrows():
        nodes.append((row["valve_id"], row["facility_id"]))
    nodes_by_fac = {}
    for node_id, fac_id in nodes:
        nodes_by_fac.setdefault(fac_id, []).append(node_id)
    pipes = []
    for fac_id, node_ids in nodes_by_fac.items():
        # Chain topology guarantees each node is linked to the next; cycles are not required.
        for j in range(len(node_ids)-1):
            pipes.append({"pipe_id": f"PIPE-{len(pipes)+1:03d}", "facility_id": fac_id,
                          "from_node_id": node_ids[j], "to_node_id": node_ids[j+1],
                          "diameter_mm": int(rng.choice([50, 75, 100, 150])),
                          "length_m": round(float(rng.uniform(5, 120)), 2), "status": "active"})
    pipes = pd.DataFrame(pipes)

    # One flow sensor per pump, one pressure sensor per facility, one level sensor per tank.
    sensors = []
    for i, p in pumps.iterrows():
        sensors.append({"sensor_id": ID("SNS", len(sensors)+1), "facility_id": p["facility_id"],
                        "component_id": p["pump_id"], "sensor_type": "flow", "unit": "L/s",
                        "measurement_role": "inlet" if i % 2 == 0 else "outlet", "status": "active"})
    for i, t in tanks.iterrows():
        sensors.append({"sensor_id": ID("SNS", len(sensors)+1), "facility_id": t["facility_id"],
                        "component_id": t["tank_id"], "sensor_type": "level", "unit": "L",
                        "measurement_role": "level", "status": "active"})
    for i, f in facilities.iterrows():
        sensors.append({"sensor_id": ID("SNS", len(sensors)+1), "facility_id": f["facility_id"],
                        "component_id": f["facility_id"], "sensor_type": "pressure", "unit": "kPa",
                        "measurement_role": "pressure", "status": "active"})
    sensors = pd.DataFrame(sensors)
    modes = pd.DataFrame([
        {"operating_mode_id": ID("MODE", i), "facility_id": ID("FAC", i),
         "mode_name": "normal", "effective_from": "2026-10-22T00:00:00Z",
         "effective_to": None, "status": "active"} for i in range(1, 4)
    ])

    # Generate telemetry in chunks so full-volume generation does not require huge intermediate arrays.
    sensor_indices = rng.integers(0, len(sensors), size=telemetry_count)
    offsets = np.arange(telemetry_count)
    start = pd.Timestamp("2026-10-22T00:00:00Z")
    timestamps = start + pd.to_timedelta(offsets, unit="s")
    telemetry_rows = []
    truth = []
    # Known scenario windows are deterministic and selected by index, not random labels.
    scenario_specs = [
        {"scenario_id":"SCN-000001","issue_type":"pump_degradation","component_id":"PUMP-003","start_index":500,"end_index":699,"expected_decision":"maintenance_inspection"},
        {"scenario_id":"SCN-000002","issue_type":"sensor_fault","component_id":"SNS-001","start_index":1000,"end_index":1099,"expected_decision":"sensor_quality_alarm"},
        {"scenario_id":"SCN-000003","issue_type":"leak","component_id":"FAC-001","start_index":1500,"end_index":1699,"expected_decision":"investigate_flow_imbalance"},
        {"scenario_id":"SCN-000004","issue_type":"blockage","component_id":"PIPE-001","start_index":2000,"end_index":2199,"expected_decision":"inspect_pressure_drop"}
    ]
    pump_map = pumps.set_index("pump_id").to_dict("index")
    sensor_map = sensors.set_index("sensor_id").to_dict("index")
    for idx in range(telemetry_count):
        # Ensure each labelled scenario actually affects its intended measurement stream.
        forced_sensor_id = None
        if 500 <= idx < 700:
            forced_sensor_id = sensors.loc[sensors["component_id"] == "PUMP-003", "sensor_id"].iloc[0]
        elif 1000 <= idx < 1100:
            forced_sensor_id = "SNS-001"
        elif 1500 <= idx < 1700:
            candidates = sensors[(sensors["facility_id"] == "FAC-001") & (sensors["sensor_type"] == "flow")]
            forced_sensor_id = candidates["sensor_id"].iloc[(idx - 1500) % len(candidates)]
        elif 2000 <= idx < 2200:
            candidates = sensors[(sensors["facility_id"] == "FAC-001") & (sensors["sensor_type"] == "pressure")]
            forced_sensor_id = candidates["sensor_id"].iloc[0]
        if forced_sensor_id is not None:
            sensor = sensors[sensors["sensor_id"] == forced_sensor_id].iloc[0]
        else:
            sensor = sensors.iloc[int(sensor_indices[idx])]
        sid = sensor["sensor_id"]
        stype = sensor["sensor_type"]
        component_id = sensor["component_id"]
        fac_id = sensor["facility_id"]
        if stype == "flow":
            pump = pump_map.get(component_id)
            nominal = float(pump["nominal_flow_lps"]) if pump else 50.0
            value = max(0.0, rng.normal(nominal, nominal*0.04))
        elif stype == "pressure":
            value = max(0.0, rng.normal(220, 12))
        else:
            tank = tanks[tanks["tank_id"] == component_id].iloc[0]
            value = float(np.clip(rng.normal(tank["initial_volume_liters"], tank["capacity_liters"]*.025),
                                  0, tank["capacity_liters"]))
        # Inject labelled, deterministic scenarios into generated feature values.
        issue = None
        for spec in scenario_specs:
            if spec["start_index"] <= idx < spec["end_index"] and (
                spec["component_id"] in (component_id, sid, fac_id) or
                (spec["issue_type"] == "blockage" and stype == "pressure" and fac_id == "FAC-001")
            ):
                issue = spec["issue_type"]
                if issue == "pump_degradation" and stype == "flow" and component_id == "PUMP-003":
                    value *= 0.55
                elif issue == "sensor_fault" and sid == "SNS-001":
                    value = 0.0
                elif issue == "leak" and fac_id == "FAC-001" and stype == "flow":
                    value *= 0.60
                elif issue == "blockage" and stype == "pressure" and fac_id == "FAC-001":
                    value *= 1.35
        telemetry_rows.append({"telemetry_id": f"TEL-{idx+1:06d}", "sensor_id": sid,
                               "timestamp": timestamps[idx].isoformat(), "facility_id": fac_id,
                               "component_id": component_id, "sensor_type": stype, "unit": sensor["unit"],
                               "measurement_role": sensor["measurement_role"], "value": round(float(value), 4),
                               "quality_status": "suspect" if issue == "sensor_fault" else "good"})
    telemetry = pd.DataFrame(telemetry_rows)

    # Ground truth is intentionally stored separately and not included in detector input features.
    for spec in scenario_specs:
        truth.append({**spec, "ground_truth": "abnormal",
                      "label_source": "documented deterministic injection rule"})
    negative_cases = {
        "invalid_pipe_reference": {"pipe_id":"PIPE-NEG-001","from_node_id":"PUMP-MISSING","to_node_id":"TANK-001","expected_validation":"missing_node"},
        "tank_over_capacity": {"tank_id":"TANK-001","level_liters":999999999,"expected_validation":"capacity_exceeded"},
        "flow_balance_violation": {"facility_id":"FAC-001","residual_lps":99.0,"tolerance_lps":8.0,"expected_validation":"balance_violation"},
        "simulation_missing_configuration": {"simulation_run_id":"SIM-NEG-001","configuration":None,"expected_validation":"missing_configuration"},
        "sensor_fault_mislabeled_as_process_fault": {"sensor_id":"SNS-001","sensor_fault":True,"expected_process_label":"unknown_until_independently_confirmed","expected_validation":"label_conflict"}
    }

    tables = {"facilities":facilities,"pumps":pumps,"tanks":tanks,"valves":valves,
              "pipes":pipes,"sensors":sensors,"operating_modes":modes,"telemetry":telemetry}
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
    (out / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    (out / "negative_cases.json").write_text(json.dumps(negative_cases, indent=2))
    manifest = {"seed":seed,"telemetry_count":telemetry_count,"generator":"app.generator.generate_dataset",
                "synthetic_only":True,"generated_at":"deterministic content; wall-clock time intentionally omitted"}
    (out / "source_manifest.json").write_text(json.dumps(manifest, indent=2))
    return {name: len(df) for name, df in tables.items()}
