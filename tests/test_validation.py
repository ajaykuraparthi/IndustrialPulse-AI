import json
import hashlib
from pathlib import Path

import pandas as pd
import pytest

from app.engine import detect_anomalies
from app.generator import generate_dataset
from app.validation import (
    FLOW_BALANCE_TOLERANCE_LPS,
    validate_dataset,
    validate_flow_balance,
    validate_simulation_record,
)

FIXTURES = Path(__file__).parent / "fixtures" / "negative_cases.json"


def negative_cases():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_generator_summary_and_manifest_report_real_artifacts(tmp_path):
    counts = generate_dataset(tmp_path, seed=17, telemetry_count=2200)
    summary = json.loads((tmp_path / "validation_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "source_manifest.json").read_text(encoding="utf-8"))

    assert summary["valid"] is True
    assert summary["counts"] == counts
    checked_intervals = summary["checks"]["flow_balance_intervals"]
    assert summary["checks"]["flow_balance_records_checked"] == 9
    assert len(checked_intervals) == 9
    assert {interval["measurement_basis"] for interval in checked_intervals} == {"modeled"}
    assert all(interval["valid"] for interval in checked_intervals)
    assert all(abs(interval["residual_lps"]) <= FLOW_BALANCE_TOLERANCE_LPS
               for interval in checked_intervals)
    assert (tmp_path / "flow_balances.csv").is_file()
    assert manifest["seed"] == 17
    assert manifest["telemetry_count"] == 2200
    assert manifest["synthetic_only"] is True
    assert "no external or operational plant data" in manifest["provenance"]
    assert "flow_balances.csv" in manifest["artifacts_sha256"]
    for filename, digest in manifest["artifacts_sha256"].items():
        assert hashlib.sha256((tmp_path / filename).read_bytes()).hexdigest() == digest
    truth = json.loads((tmp_path / "ground_truth.json").read_text(encoding="utf-8"))
    assert len(truth) == 4
    assert all(scenario["end_index"] <= 2200 for scenario in truth)


@pytest.mark.parametrize(
    ("seed", "telemetry_count"),
    [(-1, 0), (1, -1), (1.5, 10), (1, 2.5)],
)
def test_generator_rejects_invalid_scale_inputs(tmp_path, seed, telemetry_count):
    with pytest.raises(ValueError, match="seed|telemetry_count"):
        generate_dataset(tmp_path, seed=seed, telemetry_count=telemetry_count)


def test_missing_pipe_node_is_rejected_without_changing_baseline(tmp_path):
    cases = negative_cases()
    generate_dataset(tmp_path, seed=7, telemetry_count=20)
    baseline = validate_dataset(tmp_path)
    assert baseline["valid"], baseline["errors"]

    pipes_path = tmp_path / "pipes.csv"
    pipes = pd.read_csv(pipes_path)
    pipes.loc[0, "pipe_id"] = cases["missing_pipe_node"]["pipe_id"]
    pipes.loc[0, "from_node_id"] = cases["missing_pipe_node"]["from_node_id"]
    pipes.to_csv(pipes_path, index=False)
    result = validate_dataset(tmp_path)

    assert not result["valid"]
    assert any(cases["missing_pipe_node"]["expected_error"] in error for error in result["errors"])


def test_tank_level_over_capacity_is_rejected(tmp_path):
    case = negative_cases()["tank_over_capacity"]
    generate_dataset(tmp_path, seed=7, telemetry_count=20)
    tanks_path = tmp_path / "tanks.csv"
    tanks = pd.read_csv(tanks_path)
    tank_index = tanks.index[tanks["tank_id"] == case["tank_id"]][0]
    tanks.loc[tank_index, "initial_volume_liters"] = case["initial_volume_liters"]
    tanks.to_csv(tanks_path, index=False)

    result = validate_dataset(tmp_path)

    assert not result["valid"]
    assert any(case["expected_error"] in error for error in result["errors"])

    tanks.loc[tank_index, "initial_volume_liters"] = pd.read_csv(
        tmp_path / "tanks.csv"
    ).loc[tank_index, "capacity_liters"]
    tanks.to_csv(tanks_path, index=False)
    telemetry_path = tmp_path / "telemetry.csv"
    telemetry = pd.read_csv(telemetry_path)
    sensors = pd.read_csv(tmp_path / "sensors.csv")
    level_sensor = sensors[sensors["component_id"] == case["tank_id"]].iloc[0]
    telemetry.loc[0, ["sensor_id", "facility_id", "component_id", "sensor_type",
                      "unit", "measurement_role", "value"]] = [
        level_sensor["sensor_id"], level_sensor["facility_id"], case["tank_id"],
        "level", "L", "level", case["initial_volume_liters"],
    ]
    telemetry.to_csv(telemetry_path, index=False)
    telemetry_result = validate_dataset(tmp_path)
    assert not telemetry_result["valid"]
    assert any("tank level exceeds capacity" in error for error in telemetry_result["errors"])


def test_flow_balance_is_derived_and_rejected_beyond_tolerance():
    case = negative_cases()["flow_balance_violation"]
    result = validate_flow_balance(case)

    assert FLOW_BALANCE_TOLERANCE_LPS == 8.0
    assert result["residual_lps"] == pytest.approx(99.0)
    assert not result["valid"]
    balanced_with_storage = validate_flow_balance({
        **case,
        "inlet_flows_lps": [52.0],
        "outlet_flows_lps": [50.0],
        "tank_volume_change_liters": 120.0,
        "interval_seconds": 60.0,
    })
    assert balanced_with_storage["residual_lps"] == pytest.approx(0.0)
    assert balanced_with_storage["valid"]
    within_tolerance = validate_flow_balance({
        **case, "inlet_flows_lps": [51.0], "outlet_flows_lps": [50.0],
    })
    assert within_tolerance["valid"]
    at_tolerance = validate_flow_balance({
        **case, "inlet_flows_lps": [8.0], "outlet_flows_lps": [0.0],
    })
    beyond_tolerance = validate_flow_balance({
        **case, "inlet_flows_lps": [8.001], "outlet_flows_lps": [0.0],
    })
    assert at_tolerance["valid"]
    assert not beyond_tolerance["valid"]


def test_flow_balance_rejects_missing_or_invalid_measurements():
    balanced = {
        "inlet_flows_lps": [52.0],
        "outlet_flows_lps": [50.0],
        "tank_volume_change_liters": 120.0,
        "interval_seconds": 60.0,
    }
    with pytest.raises(ValueError, match="missing fields"):
        validate_flow_balance({key: value for key, value in balanced.items()
                               if key != "outlet_flows_lps"})
    with pytest.raises(ValueError, match="lists"):
        validate_flow_balance({**balanced, "inlet_flows_lps": "52.0"})
    with pytest.raises(ValueError, match="finite flows"):
        validate_flow_balance({**balanced, "outlet_flows_lps": [float("nan")]})
    with pytest.raises(ValueError, match="finite flows"):
        validate_flow_balance({**balanced, "inlet_flows_lps": [-1.0]})


def test_modeled_baseline_flows_must_match_pump_source_records(tmp_path):
    generate_dataset(tmp_path, seed=7, telemetry_count=20)
    balances_path = tmp_path / "flow_balances.csv"
    balances = pd.read_csv(balances_path)
    original = json.loads(balances.loc[0, "inlet_flows_lps"])
    original[0] += 1.0
    balances.loc[0, "inlet_flows_lps"] = json.dumps(original)
    balances.to_csv(balances_path, index=False)

    result = validate_dataset(tmp_path)

    assert not result["valid"]
    assert any("do not match modeled pump inputs" in error for error in result["errors"])


def test_flow_balance_fixture_is_checked_by_dataset_validator(tmp_path):
    case = negative_cases()["flow_balance_violation"]
    generate_dataset(tmp_path, seed=7, telemetry_count=20)
    pd.DataFrame([{
        "balance_id": "BAL-NEG-001",
        "facility_id": case["facility_id"],
        "interval_start": "2026-10-22T00:00:00Z",
        "interval_seconds": case["interval_seconds"],
        "measurement_basis": "measured",
        "inlet_flows_lps": json.dumps(case["inlet_flows_lps"]),
        "outlet_flows_lps": json.dumps(case["outlet_flows_lps"]),
        "tank_volume_change_liters": case["tank_volume_change_liters"],
    }]).to_csv(tmp_path / "flow_balances.csv", index=False)

    result = validate_dataset(tmp_path)

    assert not result["valid"]
    assert result["checks"]["flow_balance_records_checked"] == 1
    assert any(case["expected_error"] in error for error in result["errors"])


def test_simulation_without_configuration_is_rejected():
    case = negative_cases()["simulation_missing_configuration"]

    with pytest.raises(ValueError, match=case["expected_error"]):
        validate_simulation_record(case)


def test_stuck_sensor_fault_is_not_classified_as_process_fault():
    case = negative_cases()["sensor_fault_mislabeled_as_process_fault"]
    timestamps = pd.date_range("2026-01-01T00:00:00Z", periods=case["repeat_count"], freq="s")
    telemetry = pd.DataFrame({
        "sensor_id": [case["sensor_id"]] * case["repeat_count"],
        "timestamp": timestamps,
        "facility_id": [case["facility_id"]] * case["repeat_count"],
        "component_id": [case["component_id"]] * case["repeat_count"],
        "sensor_type": [case["sensor_type"]] * case["repeat_count"],
        "measurement_role": [case["measurement_role"]] * case["repeat_count"],
        "quality_status": [case["quality_status"]] * case["repeat_count"],
        "value": [case["value"]] * case["repeat_count"],
    })
    pumps = pd.DataFrame([{"pump_id": case["component_id"], "nominal_flow_lps": 80.0}])

    alarms = detect_anomalies(telemetry, pumps)
    classifications = {alarm["alarm_type"] for alarm in alarms}

    assert classifications == {"sensor_fault"}
    assert case["expected_classification"] == "sensor_fault_only"
    assert not any(alarm["alarm_type"] == "pump_degradation" for alarm in alarms)
    assert not any(alarm["alarm_type"] == "possible_leak" for alarm in alarms)


def test_stuck_pressure_sensor_does_not_trigger_process_pressure_alarm():
    values = [220.0 + index % 5 for index in range(20)]
    values.extend([300.0] * 12)
    values.extend(220.0 + index % 5 for index in range(20))
    telemetry = pd.DataFrame({
        "sensor_id": ["SNS-PRESSURE"] * len(values),
        "timestamp": pd.date_range("2026-01-01T00:00:00Z", periods=len(values), freq="s"),
        "facility_id": ["FAC-001"] * len(values),
        "component_id": ["FAC-001"] * len(values),
        "sensor_type": ["pressure"] * len(values),
        "measurement_role": ["pressure"] * len(values),
        "value": values,
        "quality_status": ["good"] * len(values),
    })

    alarms = detect_anomalies(telemetry, pd.DataFrame(columns=["pump_id", "nominal_flow_lps"]))

    assert any(alarm["alarm_type"] == "sensor_fault" for alarm in alarms)
    assert not any(alarm["alarm_type"] == "pressure_anomaly" for alarm in alarms)
