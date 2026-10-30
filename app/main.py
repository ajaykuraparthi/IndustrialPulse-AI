from __future__ import annotations
import json, sqlite3, hashlib
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from .generator import generate_dataset
from .engine import detect_anomalies
from .validation import validate_dataset

DATA = Path("data/generated")
DB = Path("industrialpulse.db")
app = FastAPI(title="IndustrialPulse AI", version="0.1.0",
              description="Synthetic industrial monitoring and simulation MVP")

def ensure_data():
    if not (DATA/"telemetry.csv").exists():
        generate_dataset(DATA, telemetry_count=5000)

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS simulation_runs (
      simulation_run_id TEXT PRIMARY KEY, facility_id TEXT NOT NULL,
      config_json TEXT NOT NULL, configuration_hash TEXT NOT NULL,
      seed INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
      output_json TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS alarms (
      alarm_id TEXT PRIMARY KEY, simulation_run_id TEXT,
      component_id TEXT NOT NULL, alarm_type TEXT NOT NULL, severity TEXT NOT NULL,
      rule_id TEXT NOT NULL, observed_value REAL, expected_value TEXT,
      explanation TEXT NOT NULL, created_at TEXT NOT NULL)""")
    conn.commit()
    return conn

class SimulationRequest(BaseModel):
    pump_id: str
    speed_pct: float = Field(ge=10, le=120)
    seed: int = 20261022

@app.get("/", response_class=HTMLResponse)
def dashboard():
    ensure_data()
    return HTMLResponse("""<!doctype html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>IndustrialPulse AI</title><style>
    body{font-family:Inter,system-ui;background:#0b1220;color:#e8eefc;margin:0;padding:28px}
    h1{margin-bottom:4px}.muted{color:#9fb0cc}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}
    .card{background:#141f33;border:1px solid #283954;border-radius:14px;padding:18px}
    button{background:#5eead4;border:0;border-radius:8px;padding:10px 14px;font-weight:700;cursor:pointer}
    input{padding:10px;background:#0b1220;border:1px solid #52617a;color:white;border-radius:8px;width:90px}
    pre{white-space:pre-wrap;overflow-wrap:anywhere}.pill{color:#5eead4}
    </style></head><body><h1>IndustrialPulse <span class="pill">AI</span></h1>
    <p class="muted">Synthetic industrial monitoring · explainable alarms · reproducible simulations</p>
    <div class="grid" id="stats"></div><h2>Run pump-speed simulation</h2>
    <div class="card"><label>Pump ID <input id="pump" value="PUMP-001"></label>
    <label>Speed % <input id="speed" type="number" min="10" max="120" value="80"></label>
    <button onclick="simulate()">Run simulation</button><pre id="result">Ready.</pre></div>
    <h2>Recent alarms</h2><div class="card"><pre id="alarms">Loading…</pre></div>
    <p class="muted">Synthetic model for evaluation only; not a safety-certified control system.</p>
    <script>
    async function load(){let s=await (await fetch('/api/summary')).json();document.getElementById('stats').innerHTML=
    Object.entries(s.counts).map(([k,v])=>`<div class="card"><div class="muted">${k.replaceAll('_',' ')}</div><h2>${v}</h2></div>`).join('');
    let a=await (await fetch('/api/alarms')).json();document.getElementById('alarms').textContent=JSON.stringify(a.slice(0,20),null,2)}
    async function simulate(){let r=await fetch('/api/simulations',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({pump_id:document.getElementById('pump').value,speed_pct:Number(document.getElementById('speed').value)})});
    document.getElementById('result').textContent=JSON.stringify(await r.json(),null,2);load()}load();
    </script></body></html>""")

@app.get("/api/summary")
def summary():
    ensure_data()
    result = validate_dataset(DATA)
    conn = db()
    alarms = conn.execute("SELECT COUNT(*) FROM alarms").fetchone()[0]
    runs = conn.execute("SELECT COUNT(*) FROM simulation_runs").fetchone()[0]
    conn.close()
    return {"counts":{**result["counts"],"active_alarms":alarms,"simulation_runs":runs},
            "validation":result}

@app.get("/api/telemetry")
def telemetry(limit: int = 100):
    ensure_data()
    df = pd.read_csv(DATA/"telemetry.csv").head(max(1,min(limit,5000)))
    return df.to_dict(orient="records")

@app.get("/api/alarms")
def alarms():
    ensure_data()
    telemetry_df = pd.read_csv(DATA/"telemetry.csv")
    pumps = pd.read_csv(DATA/"pumps.csv")
    found = detect_anomalies(telemetry_df, pumps)
    conn = db()
    now = datetime.now(timezone.utc).isoformat()
    for i, a in enumerate(found,1):
        aid = f"ALM-{i:06d}"
        conn.execute("""INSERT OR IGNORE INTO alarms
          (alarm_id,simulation_run_id,component_id,alarm_type,severity,rule_id,observed_value,
           expected_value,explanation,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
          (aid,None,a["component_id"],a["alarm_type"],a["severity"],a["rule_id"],
           a.get("observed_value"),json.dumps(a.get("expected_value")),a["explanation"],now))
    conn.commit()
    rows = conn.execute("SELECT * FROM alarms ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/simulations")
def create_simulation(req: SimulationRequest):
    ensure_data()
    pumps = pd.read_csv(DATA/"pumps.csv")
    match = pumps[pumps.pump_id == req.pump_id]
    if match.empty:
        raise HTTPException(404, "Unknown pump_id")
    pump = match.iloc[0]
    ratio = req.speed_pct / 100.0
    # Affinity-law approximation; real network operating point is not solved here.
    predicted_flow = float(pump.nominal_flow_lps * ratio)
    predicted_head = float(pump.shutoff_head_kpa * ratio**2)
    config = {"pump_id":req.pump_id,"speed_pct":req.speed_pct,"seed":req.seed,
              "model_version":"0.1.0","assumptions":"pump affinity-law approximation"}
    config_json = json.dumps(config,sort_keys=True)
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()
    sim_id = f"SIM-2026-{datetime.now(timezone.utc).strftime('%H%M%S%f')}"
    output = {"predicted_flow_lps":round(predicted_flow,3),
              "predicted_head_kpa":round(predicted_head,3),
              "baseline_flow_lps":float(pump.nominal_flow_lps),
              "flow_change_pct":round((ratio-1)*100,2),
              "note":"Simplified pump affinity-law estimate; not a hydraulic network solution."}
    conn = db()
    conn.execute("""INSERT INTO simulation_runs VALUES (?,?,?,?,?,?,?,?)""",
      (sim_id,pump.facility_id,config_json,config_hash,req.seed,"completed",
       datetime.now(timezone.utc).isoformat(),json.dumps(output)))
    conn.commit(); conn.close()
    return {"simulation_run_id":sim_id,"configuration":config,"configuration_hash":config_hash,
            "status":"completed","output":output}

@app.get("/api/simulations")
def list_simulations():
    conn=db()
    rows=conn.execute("SELECT * FROM simulation_runs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
