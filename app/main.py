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
    return HTMLResponse("""<!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>IndustrialPulse AI</title>
      <style>
        :root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;background:#0b1220;color:#e8eefc}
        *{box-sizing:border-box}
        body{margin:0;padding:clamp(16px,3vw,36px)}
        main{max-width:1440px;margin:0 auto}
        h1{margin:0 0 6px;font-size:clamp(1.7rem,4vw,2.4rem)}
        h2{margin:0 0 14px;font-size:1.25rem}
        p{line-height:1.5}
        .muted{color:#9fb0cc}
        .pill{color:#5eead4}
        .section{margin:28px 0}
        .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(190px,100%),1fr));gap:14px}
        .card,.panel{background:#141f33;border:1px solid #283954;border-radius:14px;padding:18px}
        .stat-value{margin:8px 0 0;font-size:1.7rem;overflow-wrap:anywhere}
        .section-state{margin:0 0 12px;color:#9fb0cc}
        .section-state.error{color:#fca5a5}
        .section-state.success{color:#5eead4}
        .table-wrap{max-height:460px;overflow:auto;border:1px solid #283954;border-radius:10px}
        table{width:100%;border-collapse:collapse;text-align:left;font-size:.9rem}
        th,td{padding:10px 12px;border-bottom:1px solid #283954;vertical-align:top}
        th{position:sticky;top:0;background:#1a2942;color:#cbd8ef;white-space:nowrap}
        td{overflow-wrap:anywhere}
        tbody tr:last-child td{border-bottom:0}
        pre{margin:8px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;font-size:.9rem}
        .simulation-form{display:flex;flex-wrap:wrap;align-items:end;gap:14px}
        label{display:grid;gap:6px;color:#cbd8ef}
        input{width:150px;max-width:100%;padding:10px;background:#0b1220;border:1px solid #52617a;color:#fff;border-radius:8px;font:inherit}
        button{background:#5eead4;color:#08201d;border:0;border-radius:8px;padding:11px 16px;font:inherit;font-weight:700;cursor:pointer}
        button:disabled{opacity:.55;cursor:wait}
        :focus-visible{outline:2px solid #5eead4;outline-offset:3px}
        @media(max-width:600px){.card,.panel{padding:14px}.table-wrap{max-height:360px}}
      </style>
    </head>
    <body>
      <main>
        <header>
          <h1>IndustrialPulse <span class="pill">AI</span></h1>
          <p class="muted">Synthetic industrial monitoring · explainable alarms · reproducible simulations</p>
        </header>

        <section class="section" aria-labelledby="overview-title">
          <h2 id="overview-title">Overview</h2>
          <p id="summary-state" class="section-state" role="status">Loading summary…</p>
          <div class="grid" id="stats"></div>
        </section>

        <section class="section" aria-labelledby="telemetry-title">
          <h2 id="telemetry-title">Telemetry</h2>
          <p id="telemetry-state" class="section-state" role="status">Loading telemetry…</p>
          <div class="table-wrap" tabindex="0" aria-label="Telemetry records">
            <table><thead id="telemetry-head"></thead><tbody id="telemetry-body"></tbody></table>
          </div>
        </section>

        <section class="section" aria-labelledby="alarms-title">
          <h2 id="alarms-title">Recent alarms</h2>
          <p id="alarms-state" class="section-state" role="status">Loading alarms…</p>
          <div class="table-wrap" tabindex="0" aria-label="Recent alarm records">
            <table><thead id="alarms-head"></thead><tbody id="alarms-body"></tbody></table>
          </div>
        </section>

        <section class="section" aria-labelledby="simulations-title">
          <h2 id="simulations-title">Simulation history</h2>
          <p id="simulations-state" class="section-state" role="status">Loading simulations…</p>
          <div class="table-wrap" tabindex="0" aria-label="Simulation records">
            <table><thead id="simulations-head"></thead><tbody id="simulations-body"></tbody></table>
          </div>
        </section>

        <section class="section" aria-labelledby="simulation-form-title">
          <h2 id="simulation-form-title">Run pump-speed simulation</h2>
          <div class="panel">
            <form id="simulation-form" class="simulation-form">
              <label for="pump">Pump ID
                <input id="pump" name="pump" value="PUMP-001" required>
              </label>
              <label for="speed">Speed %
                <input id="speed" name="speed" type="number" min="10" max="120" value="80" required>
              </label>
              <button id="simulate-button" type="submit">Run simulation</button>
            </form>
            <p id="simulation-result-state" class="section-state" role="status">Ready.</p>
            <pre id="simulation-result"></pre>
          </div>
        </section>

        <p class="muted">Synthetic model for evaluation only; not a safety-certified control system.</p>
      </main>
      <script>
        const byId = id => document.getElementById(id);

        function setState(id, message, kind = '') {
          const element = byId(id);
          element.textContent = message;
          element.className = kind ? `section-state ${kind}` : 'section-state';
        }

        function clear(element) {
          while (element.firstChild) element.removeChild(element.firstChild);
        }

        function displayValue(value) {
          if (value === null || value === undefined || value === '') return '—';
          return typeof value === 'object' ? JSON.stringify(value) : String(value);
        }

        function formatLabel(value) {
          return value.replaceAll('_', ' ');
        }

        async function requestJson(url, options) {
          let response;
          try {
            response = await fetch(url, options);
          } catch (error) {
            throw new Error(`Network error: ${error.message}`);
          }
          if (!response.ok) {
            throw new Error(`Request failed (${response.status}${response.statusText ? ` ${response.statusText}` : ''}).`);
          }
          try {
            return await response.json();
          } catch (error) {
            throw new Error(`Invalid JSON response: ${error.message}`);
          }
        }

        function renderTable(headId, bodyId, records, emptyMessage) {
          if (!Array.isArray(records) || records.some(record =>
            record === null || typeof record !== 'object' || Array.isArray(record))) {
            throw new Error('The server returned records in an unexpected format.');
          }
          const head = byId(headId);
          const body = byId(bodyId);
          clear(head);
          clear(body);
          if (records.length === 0) return emptyMessage;

          const columns = Object.keys(records[0]);
          const headerRow = document.createElement('tr');
          columns.forEach(column => {
            const cell = document.createElement('th');
            cell.scope = 'col';
            cell.textContent = formatLabel(column);
            headerRow.appendChild(cell);
          });
          head.appendChild(headerRow);
          records.forEach(record => {
            const row = document.createElement('tr');
            columns.forEach(column => {
              const cell = document.createElement('td');
              cell.textContent = displayValue(record[column]);
              row.appendChild(cell);
            });
            body.appendChild(row);
          });
          return '';
        }

        async function loadSummary() {
          setState('summary-state', 'Loading summary…');
          try {
            const summary = await requestJson('/api/summary');
            if (!summary || typeof summary.counts !== 'object' || summary.counts === null ||
                Array.isArray(summary.counts)) {
              throw new Error('The server returned a summary in an unexpected format.');
            }
            const stats = byId('stats');
            clear(stats);
            Object.entries(summary.counts).forEach(([key, value]) => {
              const card = document.createElement('article');
              card.className = 'card';
              const label = document.createElement('div');
              label.className = 'muted';
              label.textContent = formatLabel(key);
              const count = document.createElement('h2');
              count.className = 'stat-value';
              count.textContent = displayValue(value);
              card.append(label, count);
              stats.appendChild(card);
            });
            const validation = summary.validation;
            const validationMessage = validation && typeof validation.valid === 'boolean'
              ? ` · Dataset validation: ${validation.valid ? 'valid' : 'issues found'}`
              : '';
            setState('summary-state', `Summary loaded${validationMessage}.`, validation && validation.valid === false ? 'error' : 'success');
          } catch (error) {
            setState('summary-state', error.message || 'Unable to load summary.', 'error');
          }
        }

        async function loadTelemetry() {
          setState('telemetry-state', 'Loading telemetry…');
          try {
            const records = await requestJson('/api/telemetry');
            const emptyMessage = renderTable('telemetry-head', 'telemetry-body', records, 'No telemetry records are available.');
            setState('telemetry-state', emptyMessage || `Showing ${records.length} telemetry records returned by the API.`, emptyMessage ? '' : 'success');
          } catch (error) {
            setState('telemetry-state', error.message || 'Unable to load telemetry.', 'error');
          }
        }

        async function loadAlarms() {
          setState('alarms-state', 'Loading alarms…');
          try {
            const records = await requestJson('/api/alarms');
            if (!Array.isArray(records)) throw new Error('The server returned alarms in an unexpected format.');
            const emptyMessage = renderTable('alarms-head', 'alarms-body', records.slice(0, 20), 'No alarm records are available.');
            setState('alarms-state', emptyMessage || `Showing the latest ${Math.min(records.length, 20)} of ${records.length} alarm records.`, emptyMessage ? '' : 'success');
          } catch (error) {
            setState('alarms-state', error.message || 'Unable to load alarms.', 'error');
          }
        }

        function parseStoredJson(value) {
          if (typeof value !== 'string') return value;
          try {
            return JSON.parse(value);
          } catch {
            return value;
          }
        }

        async function loadSimulations() {
          setState('simulations-state', 'Loading simulation history…');
          try {
            const records = await requestJson('/api/simulations');
            if (!Array.isArray(records)) throw new Error('The server returned simulation history in an unexpected format.');
            const rows = records.map(record => {
              if (!record || typeof record !== 'object' || Array.isArray(record)) {
                throw new Error('The server returned a simulation record in an unexpected format.');
              }
              const configuration = parseStoredJson(record.config_json) || {};
              const output = parseStoredJson(record.output_json);
              const scenario = configuration && typeof configuration === 'object'
                ? [configuration.scenario, configuration.speed_pct === undefined ? '' : `Pump speed: ${configuration.speed_pct}%`,
                    configuration.assumptions].filter(Boolean).join(' · ')
                : displayValue(record.config_json);
              return {
                simulation_run_id: record.simulation_run_id,
                facility_id: record.facility_id,
                equipment: configuration && configuration.pump_id ? configuration.pump_id : '—',
                scenario: scenario || '—',
                status: record.status,
                created_at: record.created_at,
                results: output
              };
            });
            const emptyMessage = renderTable('simulations-head', 'simulations-body', rows, 'No simulations have been run yet.');
            setState('simulations-state', emptyMessage || `Showing ${records.length} simulation records.`, emptyMessage ? '' : 'success');
          } catch (error) {
            setState('simulations-state', error.message || 'Unable to load simulation history.', 'error');
          }
        }

        byId('simulation-form').addEventListener('submit', async event => {
          event.preventDefault();
          const form = event.currentTarget;
          const button = byId('simulate-button');
          if (button.disabled || !form.reportValidity()) return;

          const controls = Array.from(form.elements);
          controls.forEach(control => { control.disabled = true; });
          button.textContent = 'Running…';
          setState('simulation-result-state', 'Submitting simulation…');
          byId('simulation-result').textContent = '';
          try {
            const result = await requestJson('/api/simulations', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({
                pump_id: byId('pump').value,
                speed_pct: Number(byId('speed').value)
              })
            });
            byId('simulation-result').textContent = JSON.stringify(result, null, 2);
            setState('simulation-result-state', 'Simulation completed.', 'success');
            await Promise.all([loadSummary(), loadSimulations()]);
          } catch (error) {
            setState('simulation-result-state', error.message || 'Unable to create simulation.', 'error');
          } finally {
            controls.forEach(control => { control.disabled = false; });
            button.textContent = 'Run simulation';
          }
        });

        loadTelemetry();
        loadSimulations();
        loadAlarms().then(loadSummary);
      </script>
    </body>
    </html>""")

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
