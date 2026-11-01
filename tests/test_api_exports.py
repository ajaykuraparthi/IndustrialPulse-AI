import csv
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main as api
from app.exports import export_seed_json, export_seed_sql, export_simulation_results
from app.generator import generate_dataset


def test_seed_sql_round_trips_into_fresh_sqlite(tmp_path):
    data_dir = tmp_path / "generated"
    generate_dataset(data_dir, seed=41, telemetry_count=80)
    sql_path = export_seed_sql(data_dir, tmp_path / "first.sql")
    repeated_path = export_seed_sql(data_dir, tmp_path / "second.sql")
    assert sql_path.read_bytes() == repeated_path.read_bytes()
    json_path = export_seed_json(data_dir, tmp_path / "seed.json")
    repeated_json = export_seed_json(data_dir, tmp_path / "seed-again.json")
    assert json_path.read_bytes() == repeated_json.read_bytes()
    seed_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert set(seed_json) == {
        "facilities", "pumps", "tanks", "valves", "pipes", "sensors",
        "operating_modes", "telemetry",
    }
    assert len(seed_json["facilities"]) == 3
    assert len(seed_json["pumps"]) == 20
    assert len(seed_json["tanks"]) == 30
    assert len(seed_json["valves"]) == 60
    assert len(seed_json["telemetry"]) == 80
    assert seed_json["pumps"][0]["pump_id"] == "PUMP-001"
    assert seed_json["telemetry"][0]["telemetry_id"] == "TEL-000001"

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(sql_path.read_text(encoding="utf-8"))
    counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "facilities", "pumps", "tanks", "valves", "pipes", "sensors",
            "operating_modes", "telemetry",
        )
    }
    assert counts == {
        "facilities": 3,
        "pumps": 20,
        "tanks": 30,
        "valves": 60,
        "pipes": 107,
        "sensors": 53,
        "operating_modes": 3,
        "telemetry": 80,
    }
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute(
        "SELECT COUNT(*) FROM telemetry WHERE telemetry_id = 'TEL-000001'"
    ).fetchone()[0] == 1
    connection.close()


def test_api_validation_database_history_and_result_exports(tmp_path, monkeypatch):
    data_dir = tmp_path / "generated"
    generate_dataset(data_dir, seed=23, telemetry_count=100)
    database_path = tmp_path / "runtime.db"
    monkeypatch.setattr(api, "DATA", data_dir)
    monkeypatch.setattr(api, "DB", database_path)
    client = TestClient(api.app)

    for speed in (9, 121):
        response = client.post(
            "/api/simulations",
            json={"pump_id": "PUMP-001", "speed_pct": speed},
        )
        assert response.status_code == 422
    response = client.post(
        "/api/simulations",
        content='{"pump_id":"PUMP-001","speed_pct":NaN}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    for body in ({"pump_id": "", "speed_pct": 80}, {"pump_id": "PUMP-001"}):
        response = client.post("/api/simulations", json=body)
        assert response.status_code == 422
    response = client.post(
        "/api/simulations",
        json={"pump_id": "PUMP-404", "speed_pct": 80},
    )
    assert response.status_code == 404
    assert client.post(
        "/api/simulations", json={"pump_id": "PUMP-001", "speed_pct": 10}
    ).status_code == 200
    assert client.post(
        "/api/simulations", json={"pump_id": "PUMP-001", "speed_pct": 120}
    ).status_code == 200

    history = client.get("/api/simulations").json()
    assert len(history) == 2
    assert history[0]["simulation_run_id"] != history[1]["simulation_run_id"]
    for record in history:
        config = json.loads(record["config_json"])
        output = json.loads(record["output_json"])
        assert config["simulation_run_id"] == record["simulation_run_id"]
        assert config["pump_id"] == record["pump_id"] == "PUMP-001"
        assert config["seed"] == record["seed"]
        assert config["assumptions"]
        assert output["predicted_flow_lps"] > 0

    conn = sqlite3.connect(database_path)
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO simulation_runs
            (simulation_run_id, facility_id, pump_id, config_json, configuration_hash,
             seed, status, created_at, output_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("SIM-NO-CONFIG", "FAC-001", "PUMP-001", "{}", "0" * 64, 1,
             "completed", "now", json.dumps({
                 "predicted_flow_lps": 50, "predicted_head_kpa": 200,
             })),
        )
    invalid_config = {
        "simulation_run_id": "SIM-BAD-REFERENCE",
        "pump_id": "PUMP-MISSING",
        "seed": 1,
        "assumptions": "test",
    }
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO simulation_runs
            (simulation_run_id, facility_id, pump_id, config_json, configuration_hash,
             seed, status, created_at, output_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("SIM-BAD-REFERENCE", "FAC-001", "PUMP-MISSING",
             json.dumps(invalid_config), "0" * 64, 1, "completed", "now",
             json.dumps({"predicted_flow_lps": 50, "predicted_head_kpa": 200})),
        )
    conn.execute(
        """INSERT INTO alarms
        (alarm_id, simulation_run_id, component_id, alarm_type, severity, rule_id,
         observed_value, expected_value, explanation, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("ALM-EXPORT-001", history[0]["simulation_run_id"], "PUMP-001",
         "pump_degradation", "high", "PUMP_PERFORMANCE_RATIO", 20.0,
         json.dumps(80.0), "Synthetic export test alarm", "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    export_dir = tmp_path / "exports"
    exports = export_simulation_results(database_path, export_dir)
    assert all(path.is_file() for path in exports.values())
    run_json = json.loads(exports["simulation_runs_json"].read_text(encoding="utf-8"))
    alarm_json = json.loads(exports["alarms_json"].read_text(encoding="utf-8"))
    assert len(run_json) == 2
    assert {row["simulation_run_id"] for row in run_json} == {
        row["simulation_run_id"] for row in history
    }
    assert len(alarm_json) == 1
    assert alarm_json[0]["alarm_id"] == "ALM-EXPORT-001"
    assert alarm_json[0]["simulation_run_id"] in {
        row["simulation_run_id"] for row in history
    }
    with exports["simulation_runs_csv"].open(encoding="utf-8", newline="") as file:
        run_csv = list(csv.DictReader(file))
    with exports["alarms_csv"].open(encoding="utf-8", newline="") as file:
        alarm_reader = csv.DictReader(file)
        assert "alarm_id" in alarm_reader.fieldnames
        alarm_csv = list(alarm_reader)
    assert len(alarm_csv) == 1
    assert alarm_csv[0]["alarm_id"] == "ALM-EXPORT-001"
    assert len(run_csv) == 2
    assert "config_json" in run_csv[0]
    assert "output_json" in run_csv[0]
    assert json.loads(run_csv[0]["config_json"])["simulation_run_id"] in {
        row["simulation_run_id"] for row in history
    }

    repeated = export_simulation_results(database_path, tmp_path / "exports-again")
    for name in exports:
        assert exports[name].read_bytes() == repeated[name].read_bytes()


def test_legacy_database_migration_preserves_simulation_history(tmp_path, monkeypatch):
    data_dir = tmp_path / "generated"
    generate_dataset(data_dir, seed=3, telemetry_count=20)
    database_path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(database_path)
    legacy.execute("""CREATE TABLE simulation_runs (
      simulation_run_id TEXT PRIMARY KEY, facility_id TEXT NOT NULL,
      config_json TEXT NOT NULL, configuration_hash TEXT NOT NULL,
      seed INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
      output_json TEXT NOT NULL)""")
    legacy.execute(
        "INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("SIM-LEGACY", "FAC-001", json.dumps({"pump_id": "PUMP-001"}),
         "a" * 64, 20261022, "completed", "2026-01-01T00:00:00Z", "{}"),
    )
    legacy.commit()
    legacy.close()
    monkeypatch.setattr(api, "DATA", data_dir)
    monkeypatch.setattr(api, "DB", database_path)

    conn = api.db()
    migrated = conn.execute(
        "SELECT simulation_run_id, pump_id FROM simulation_runs"
    ).fetchall()
    conn.close()

    assert [(row["simulation_run_id"], row["pump_id"]) for row in migrated] == [
        ("SIM-LEGACY", "PUMP-001")
    ]
