import json
from pathlib import Path
import pandas as pd
import pytest
from app.generator import generate_dataset
from app.validation import validate_dataset
from app.engine import detect_anomalies
from evaluate_scenarios import match_scenario

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
    generate_dataset(tmp_path,seed=20261022,telemetry_count=2500)
    truth=json.loads((tmp_path/"ground_truth.json").read_text())
    telemetry=pd.read_csv(tmp_path/"telemetry.csv")
    assert len(truth) == 4
    assert all(scenario["end_index"] <= len(telemetry) for scenario in truth)
    assert "ground_truth" not in telemetry.columns
    assert not (tmp_path/"negative_cases.json").exists()

def test_detector_sensor_fault_rule():
    timestamps = pd.date_range(
        "2026-01-01T00:00:00Z",
        periods=20,
        freq="s"
    )

    # The sensor behaves normally, freezes for eight readings,
    # and then starts changing again.
    values = [
        50.0, 51.0, 49.0, 52.0, 50.0, 48.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        51.0, 50.0, 52.0, 49.0, 51.0, 50.0
    ]

    telemetry = pd.DataFrame({
        "sensor_id": ["SNS-X"] * 20,
        "timestamp": timestamps,
        "component_id": ["PUMP-X"] * 20,
        "sensor_type": ["flow"] * 20,
        "value": values,
        "measurement_role": ["inlet"] * 20,
        "facility_id": ["FAC-001"] * 20
    })

    pumps = pd.DataFrame(columns=["pump_id", "nominal_flow_lps"])

    alarms = detect_anomalies(telemetry, pumps)

    assert any(
        alarm["alarm_type"] == "sensor_fault"
        and alarm["rule_id"] == "SENSOR_STUCK_VALUE"
        and alarm["sensor_id"] == "SNS-X"
        and alarm["component_id"] == "PUMP-X"
        and alarm["window_start"] == timestamps[6].isoformat()
        for alarm in alarms
    ), "The detector should identify a frozen sensor within a longer time series."

def test_detector_pump_degradation_rule():
    values = [96.0 + index % 5 for index in range(20)]
    values.extend(55.0 + index % 5 for index in range(15))
    values.extend(97.0 + index % 5 for index in range(20))
    telemetry = pd.DataFrame({
        "sensor_id": ["SNS-P"] * len(values),
        "timestamp": pd.date_range(
            "2026-01-01T00:00:00Z", periods=len(values), freq="s"
        ),
        "component_id": ["PUMP-001"] * len(values),
        "sensor_type": ["flow"] * len(values),
        "value": values,
        "measurement_role": ["inlet"] * len(values),
        "facility_id": ["FAC-001"] * len(values)
    })

    pumps = pd.DataFrame([{
        "pump_id": "PUMP-001",
        "nominal_flow_lps": 80.0
    }])

    alarms = detect_anomalies(telemetry, pumps)

    assert any(
        a["alarm_type"] == "pump_degradation"
        and a["rule_id"] == "PUMP_PERFORMANCE_RATIO"
        and a["sensor_id"] == "SNS-P"
        and a["window_start"] == telemetry.timestamp.iloc[20].isoformat()
        and a["window_end"] == telemetry.timestamp.iloc[34].isoformat()
        for a in alarms
    )


def test_detector_negative_physical_reading():
    telemetry = pd.DataFrame([{
        "sensor_id": "SNS-N",
        "timestamp": "2026-01-01T00:00:00Z",
        "component_id": "PUMP-001",
        "sensor_type": "flow",
        "value": -5.0,
        "measurement_role": "inlet",
        "facility_id": "FAC-001"
    }])

    pumps = pd.DataFrame(columns=["pump_id", "nominal_flow_lps"])

    alarms = detect_anomalies(telemetry, pumps)

    assert any(
        a["alarm_type"] == "sensor_fault"
        and a["rule_id"] == "NEGATIVE_PHYSICAL_READING"
        for a in alarms
    )

def test_detector_possible_leak_rule():
    rows = []
    for index in range(80):
        pump_number = index % 6 + 1
        role = "inlet" if pump_number % 2 else "outlet"
        rows.append({
            "sensor_id": f"SNS-{pump_number}",
            "timestamp": pd.Timestamp("2026-01-01T00:00:00Z") + pd.Timedelta(seconds=index),
            "component_id": f"PUMP-{pump_number}",
            "sensor_type": "flow",
            "value": (100.0 if index < 20 else 60.0) + index % 5,
            "measurement_role": role,
            "facility_id": "FAC-001",
        })
    telemetry = pd.DataFrame(rows)
    pumps = pd.DataFrame([{
        "pump_id": f"PUMP-{index}",
        "nominal_flow_lps": 100.0,
    } for index in range(1, 7)])

    alarms = detect_anomalies(telemetry, pumps)

    assert any(
        a["alarm_type"] == "possible_leak"
        and a["rule_id"] == "FACILITY_FLOW_DEPRESSION_PROXY"
        and a["component_id"] == "FAC-001"
        and len(a["sensor_ids"]) >= 3
        for a in alarms
    )
    assert not any(a["alarm_type"] == "pump_degradation" for a in alarms)


def test_pressure_readings_are_available_for_future_blockage_rule():
    telemetry = pd.DataFrame({
        "sensor_id": ["SNS-PRESSURE"] * 5,
        "timestamp": pd.date_range(
            "2026-01-01T00:00:00Z", periods=5, freq="s"
        ),
        "component_id": ["FAC-001"] * 5,
        "sensor_type": ["pressure"] * 5,
        "value": [300.0, 305.0, 310.0, 315.0, 320.0],
        "measurement_role": ["pressure"] * 5,
        "facility_id": ["FAC-001"] * 5
    })

    assert (telemetry["sensor_type"] == "pressure").all()
    assert telemetry["value"].max() == 320.0

def test_detector_sustained_high_pressure():
    timestamps = pd.date_range(
        "2026-01-01T00:00:00Z",
        periods=40,
        freq="s"
    )

    values = [220.0 + index % 5 for index in range(20)]
    values.extend(300.0 + index % 5 for index in range(20))

    telemetry = pd.DataFrame({
        "sensor_id": ["SNS-PRESSURE"] * 40,
        "timestamp": timestamps,
        "component_id": ["FAC-001"] * 40,
        "sensor_type": ["pressure"] * 40,
        "value": values,
        "measurement_role": ["pressure"] * 40,
        "facility_id": ["FAC-001"] * 40
    })

    pumps = pd.DataFrame(columns=["pump_id", "nominal_flow_lps"])

    alarms = detect_anomalies(telemetry, pumps)

    assert any(
        alarm["alarm_type"] == "pressure_anomaly"
        and alarm["rule_id"] == "SUSTAINED_HIGH_PRESSURE"
        and alarm["sensor_id"] == "SNS-PRESSURE"
        and alarm["window_start"] == timestamps[20].isoformat()
        and alarm["window_end"] == timestamps[-1].isoformat()
        for alarm in alarms
    )


def test_normal_telemetry_does_not_generate_process_alarms():
    rows = []
    for index in range(120):
        pump_number = index % 6 + 1
        rows.append({
            "sensor_id": f"SNS-{pump_number}",
            "timestamp": pd.Timestamp("2026-01-01T00:00:00Z") + pd.Timedelta(seconds=index),
            "component_id": f"PUMP-{pump_number}",
            "sensor_type": "flow",
            "value": 98.0 + index % 5,
            "measurement_role": "inlet" if pump_number % 2 else "outlet",
            "facility_id": "FAC-001",
        })
    telemetry = pd.DataFrame(rows)
    pumps = pd.DataFrame([{
        "pump_id": f"PUMP-{index}",
        "nominal_flow_lps": 100.0,
    } for index in range(1, 7)])

    alarms = detect_anomalies(telemetry, pumps)

    assert not any(alarm["alarm_type"] in {
        "pump_degradation", "possible_leak", "pressure_anomaly"
    } for alarm in alarms)


def test_suspect_sensor_fault_does_not_become_pump_degradation():
    telemetry = pd.DataFrame({
        "sensor_id": ["SNS-001"] * 12,
        "timestamp": pd.date_range("2026-01-01T00:00:00Z", periods=12, freq="s"),
        "component_id": ["PUMP-001"] * 12,
        "sensor_type": ["flow"] * 12,
        "value": [0.0] * 12,
        "measurement_role": ["inlet"] * 12,
        "facility_id": ["FAC-001"] * 12,
        "quality_status": ["suspect"] * 12,
    })
    pumps = pd.DataFrame([{"pump_id": "PUMP-001", "nominal_flow_lps": 80.0}])

    alarms = detect_anomalies(telemetry, pumps)

    assert any(alarm["rule_id"] == "SENSOR_STUCK_VALUE" for alarm in alarms)
    assert not any(alarm["alarm_type"] == "pump_degradation" for alarm in alarms)


def test_detector_reports_malformed_telemetry():
    telemetry = pd.DataFrame([{
        "sensor_id": "SNS-BAD",
        "timestamp": "not-a-timestamp",
        "component_id": "PUMP-001",
        "sensor_type": "flow",
        "value": "not-a-number",
        "measurement_role": "inlet",
        "facility_id": "FAC-001",
    }])

    with pytest.raises(ValueError, match="malformed rows"):
        detect_anomalies(telemetry, pd.DataFrame(columns=["pump_id", "nominal_flow_lps"]))


def test_scenario_evaluation_uses_sensor_mapping_and_facility_proxy():
    sensors = pd.DataFrame([{"sensor_id": "SNS-001", "component_id": "PUMP-001"}])
    pipes = pd.DataFrame([{"pipe_id": "PIPE-001", "facility_id": "FAC-001"}])
    start = pd.Timestamp("2026-01-01T00:00:00Z")
    end = pd.Timestamp("2026-01-01T00:01:00Z")
    alarms = [{
        "sensor_id": "SNS-001",
        "component_id": "PUMP-001",
        "alarm_type": "sensor_fault",
        "rule_id": "SENSOR_STUCK_VALUE",
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
    }]

    sensor_matches = match_scenario(
        {"issue_type": "sensor_fault", "component_id": "SNS-001"},
        alarms, start, end, sensors, pipes,
    )
    assert sensor_matches == [(0, "exact_target")]

    blockage_matches = match_scenario(
        {"issue_type": "blockage", "component_id": "PIPE-001"},
        [{**alarms[0], "sensor_id": "SNS-PRESSURE", "component_id": "FAC-001",
          "alarm_type": "pressure_anomaly", "rule_id": "SUSTAINED_HIGH_PRESSURE"}],
        start, end, sensors, pipes,
    )
    assert blockage_matches == [(0, "facility_proxy")]
