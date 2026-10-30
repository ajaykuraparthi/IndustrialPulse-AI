
"""Evaluate detector alarms against separately stored injected scenarios."""
import json
import sys
from pathlib import Path

import pandas as pd

from app.engine import detect_anomalies

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data" / "generated"


def load_inputs(data_dir: Path = DATA_DIR):
    """Load the documented evaluation inputs with actionable failures."""
    paths = {
        "telemetry": data_dir / "telemetry.csv",
        "pumps": data_dir / "pumps.csv",
        "sensors": data_dir / "sensors.csv",
        "pipes": data_dir / "pipes.csv",
        "ground truth": data_dir / "ground_truth.json",
    }
    for label, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(
                f"Required {label} file not found: {path}. "
                "Generate the dataset with python generate_data.py first."
            )

    try:
        telemetry = pd.read_csv(paths["telemetry"])
        pumps = pd.read_csv(paths["pumps"])
        sensors = pd.read_csv(paths["sensors"])
        pipes = pd.read_csv(paths["pipes"])
        with paths["ground truth"].open("r", encoding="utf-8") as file:
            ground_truth = json.load(file)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError,
            UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not load evaluation data: {error}") from error

    if not isinstance(ground_truth, list):
        raise ValueError("ground_truth.json must contain a list of scenario records")
    required = {
        "telemetry": {
            "telemetry_id", "sensor_id", "timestamp", "facility_id", "component_id",
            "sensor_type", "unit", "measurement_role", "value", "quality_status",
        },
        "pumps": {"pump_id", "nominal_flow_lps"},
        "sensors": {"sensor_id", "component_id"},
        "pipes": {"pipe_id", "facility_id"},
    }
    for name, frame in (("telemetry", telemetry), ("pumps", pumps),
                        ("sensors", sensors), ("pipes", pipes)):
        missing = required[name] - set(frame.columns)
        if missing:
            raise ValueError(
                f"{paths[name].name} is missing required columns: "
                + ", ".join(sorted(missing))
            )
    if telemetry.empty:
        raise ValueError(f"No telemetry records found in {paths['telemetry']}")
    return telemetry, pumps, sensors, pipes, ground_truth


def match_scenario(scenario, alarms, window_start, window_end, sensors, pipes):
    """Return (alarm index, match kind) pairs for one scenario and its window."""
    issue_type = scenario["issue_type"]
    target_id = scenario["component_id"]
    expected_type = {
        "pump_degradation": "pump_degradation",
        "sensor_fault": "sensor_fault",
        "leak": "possible_leak",
        "blockage": "pressure_anomaly",
    }.get(issue_type)
    if expected_type is None:
        raise ValueError(f"Unsupported scenario issue_type: {issue_type}")

    monitored_component = None
    target_facility = None
    if issue_type == "sensor_fault":
        sensor_rows = sensors[sensors["sensor_id"] == target_id]
        if len(sensor_rows) != 1:
            raise ValueError(f"Scenario sensor target {target_id} is missing or ambiguous in sensors.csv")
        monitored_component = sensor_rows.iloc[0]["component_id"]
    elif issue_type == "blockage":
        pipe_rows = pipes[pipes["pipe_id"] == target_id]
        if len(pipe_rows) != 1:
            raise ValueError(f"Scenario pipe target {target_id} is missing or ambiguous in pipes.csv")
        target_facility = pipe_rows.iloc[0]["facility_id"]

    matches = []
    for alarm_index, alarm in enumerate(alarms):
        if alarm.get("alarm_type") != expected_type:
            continue
        alarm_start_value = alarm.get("window_start", alarm.get("timestamp"))
        alarm_end_value = alarm.get("window_end", alarm.get("timestamp"))
        try:
            alarm_start = pd.to_datetime(alarm_start_value, utc=True, errors="raise")
            alarm_end = pd.to_datetime(alarm_end_value, utc=True, errors="raise")
        except (TypeError, ValueError) as error:
            raise ValueError(f"Alarm {alarm_index + 1} has an invalid timestamp window") from error
        if alarm_start > window_end or alarm_end < window_start:
            continue

        if issue_type == "pump_degradation":
            if alarm.get("component_id") == target_id:
                matches.append((alarm_index, "exact_target"))
        elif issue_type == "sensor_fault":
            if (alarm.get("sensor_id") == target_id
                    and alarm.get("component_id") == monitored_component):
                matches.append((alarm_index, "exact_target"))
        elif issue_type == "leak":
            if (alarm.get("component_id") == target_id
                    and alarm.get("rule_id") == "FACILITY_FLOW_DEPRESSION_PROXY"):
                matches.append((alarm_index, "facility_proxy"))
        elif issue_type == "blockage":
            if alarm.get("component_id") == target_facility:
                matches.append((alarm_index, "facility_proxy"))
    return matches


def evaluate_scenarios(telemetry, alarms, sensors, pipes, ground_truth):
    """Match alarms only after detection, using documented exclusive index windows."""
    timestamps = pd.to_datetime(telemetry["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any():
        raise ValueError("Cannot evaluate scenario windows: telemetry has invalid timestamps")
    if not timestamps.is_monotonic_increasing:
        raise ValueError(
            "Cannot evaluate index-based scenario windows: telemetry rows are not timestamp ordered"
        )

    results = []
    matched_alarm_indices = set()
    for scenario in ground_truth:
        try:
            start_index = int(scenario["start_index"])
            end_index = int(scenario["end_index"])
            scenario_id = scenario["scenario_id"]
            issue_type = scenario["issue_type"]
            target_id = scenario["component_id"]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid ground-truth scenario record: {scenario!r}") from error
        if start_index < 0 or end_index <= start_index or end_index > len(telemetry):
            raise ValueError(
                f"Scenario {scenario_id} has invalid exclusive row window "
                f"[{start_index}, {end_index}) for {len(telemetry)} telemetry rows"
            )
        window_start = timestamps.iloc[start_index]
        window_end = timestamps.iloc[end_index - 1]
        matches = match_scenario(
            scenario, alarms, window_start, window_end, sensors, pipes
        )
        matched_alarm_indices.update(index for index, _ in matches)
        results.append({
            "scenario_id": scenario_id,
            "issue_type": issue_type,
            "target_id": target_id,
            "matches": matches,
            "window_start": window_start,
            "window_end": window_end,
        })

    unexpected = [
        index for index in range(len(alarms)) if index not in matched_alarm_indices
    ]
    return results, unexpected


def format_alarm(alarm):
    sensor_id = alarm.get("sensor_id")
    sensor_ids = alarm.get("sensor_ids")
    sensor_text = sensor_id if sensor_id is not None else (
        ", ".join(sensor_ids) if sensor_ids else "not available"
    )
    start = alarm.get("window_start", alarm.get("timestamp", "not available"))
    end = alarm.get("window_end", alarm.get("timestamp", "not available"))
    return (
        f"Rule: {alarm.get('rule_id', 'unknown')} | "
        f"Type: {alarm.get('alarm_type', 'unknown')} | "
        f"Severity: {alarm.get('severity', 'unknown')} | "
        f"Sensor(s): {sensor_text} | "
        f"Component: {alarm.get('component_id', 'unknown')} | "
        f"Window: {start} to {end}\n"
        f"  Explanation: {alarm.get('explanation', 'not available')}"
    )


def main():
    telemetry, pumps, sensors, pipes, ground_truth = load_inputs()
    print("Running anomaly detection without ground-truth labels...")
    alarms = detect_anomalies(telemetry, pumps)
    results, unexpected = evaluate_scenarios(
        telemetry, alarms, sensors, pipes, ground_truth
    )

    print("\n========== ALARMS ==========")
    print(f"Telemetry rows: {len(telemetry)} | Scenarios: {len(results)} | Alarms: {len(alarms)}")
    if not alarms:
        print("No alarms detected.")
    for index, alarm in enumerate(alarms, start=1):
        print(f"\nAlarm {index}: {format_alarm(alarm)}")

    print("\n========== SCENARIO RESULTS ==========")
    detected = 0
    exact = 0
    proxy = 0
    missed = 0
    for result in results:
        matches = result["matches"]
        if not matches:
            missed += 1
            status = "MISSED"
        else:
            detected += 1
            kinds = {kind for _, kind in matches}
            if "exact_target" in kinds:
                exact += 1
                status = "DETECTED: EXACT TARGET"
            else:
                proxy += 1
                status = "DETECTED: FACILITY-LEVEL PROXY"
        print(
            f"\n{result['scenario_id']} {result['issue_type']} target="
            f"{result['target_id']}: {status}"
        )
        print(
            f"  Scenario window: {result['window_start'].isoformat()} to "
            f"{result['window_end'].isoformat()}"
        )
        for alarm_index, _ in matches:
            print(f"  Matched alarm {alarm_index + 1}: {alarms[alarm_index]['rule_id']}")

    print("\n========== UNEXPECTED ALARMS ==========")
    if not unexpected:
        print("None")
    for alarm_index in unexpected:
        print(f"\nAlarm {alarm_index + 1}: {format_alarm(alarms[alarm_index])}")

    print(
        f"\nSummary: {detected} detected ({exact} exact, {proxy} facility proxy), "
        f"{missed} missed, {len(unexpected)} unexpected alarms."
    )
    print("These scenario screening counts are not precision, recall, or F1 metrics.")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as error:
        print(f"Evaluation error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
