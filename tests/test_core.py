import json
from pathlib import Path
import pandas as pd
from app.generator import generate_dataset
from app.validation import validate_dataset
from app.engine import detect_anomalies

def test_generator_counts_and_relationships(tmp_path):
    counts=generate_dataset(tmp_path,seed=123,telemetry_count=300)
    assert counts["facilities"] == 3
    assert counts["pumps"] == 20
    assert counts["tanks"] == 30
    assert counts["valves"] == 60
    assert counts["telemetry"] == 300
    result=validate_dataset(tmp_path)
    assert result["valid"], result["errors"]

def test_ground_truth_is_separate(tmp_path):
    generate_dataset(tmp_path,seed=20261022,telemetry_count=300)
    truth=json.loads((tmp_path/"ground_truth.json").read_text())
    telemetry=pd.read_csv(tmp_path/"telemetry.csv")
    assert len(truth) >= 4
    assert "ground_truth" not in telemetry.columns

def test_detector_sensor_fault_rule():
    telemetry=pd.DataFrame([{
        "sensor_id":"SNS-X","timestamp":f"2026-01-01T00:00:{i:02d}Z",
        "component_id":"PUMP-X","sensor_type":"flow","value":0.0,
        "measurement_role":"inlet","facility_id":"FAC-001"
    } for i in range(10)])
    pumps=pd.DataFrame(columns=["pump_id","nominal_flow_lps"])
    alarms=detect_anomalies(telemetry,pumps)
    assert any(a["alarm_type"]=="sensor_fault" for a in alarms)
