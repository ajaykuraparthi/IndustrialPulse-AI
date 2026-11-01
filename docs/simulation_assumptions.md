# Simulation Assumptions and Modeling Limitations

## 1. Data Provenance and Units

1. **Synthetic data only.** All baseline data and scenario injections are generated locally. No operational plant data is used.
2. **Units and time.** Flow is expressed in litres per second (L/s), pressure in kilopascals (kPa), tank volume in litres (L), and timestamps in UTC.
3. **Reproducible generation.** `app.generator.generate_dataset` uses seeded NumPy draws and deterministic scenario injection. No third-party, licensed, or operational plant dataset is ingested. The source manifest records the seed, telemetry count, and SHA-256 checksums for generated artifacts.

## 2. Pump and Speed-Change Model

4. **Approximate pump curve.** The pump curve is represented by the simplified relationship:

   `H(Q) = H₀ - kQ²`

   Here, `H₀` is the shutoff-head reference, `Q` is flow, and `k` is a model coefficient. This approximation is not a calibrated pump performance curve.

5. **Pump affinity approximations.** Changes in pump speed use:

   - `Q₂ / Q₁ ≈ N₂ / N₁`
   - `H₂ / H₁ ≈ (N₂ / N₁)²`

   where `Q` denotes flow, `H` denotes head, and `N` denotes rotational speed. These relationships are used as approximations, not as a complete hydraulic model.

6. **Pump-only simulation.** The simulation endpoint estimates output for an individual pump. It does not solve the entire network's hydraulic operating point, model all network interactions, or calculate a system-wide pressure/flow distribution.

## 3. Scenario Labels and Sensor Quality

7. **Ground-truth separation.** Leak and blockage labels are scenario metadata used for post-detection evaluation. Detection rules do not read ground-truth files. In `ground_truth.json`, `component_id` is a legacy target-ID field whose identifier namespace depends on `issue_type`; it may identify different kinds of targets across scenarios.

8. **Sensor faults versus process faults.** A sensor fault indicates a problem with measurement quality. It is not, by itself, proof of an underlying process fault. `suspect` telemetry and detected sensor-fault windows are excluded from process-anomaly rules.

9. **Illustrative thresholds.** All thresholds are prototype settings. They must be calibrated, independently validated, and reviewed for safety before any real-world use.

## 4. Detection Rules and Thresholds

10. **Pump-degradation screening.** The detector screens for pump degradation when one sensor stream contains at least 10 consecutive good readings below 75% of that pump's nominal flow. `suspect` readings and readings in detected sensor-fault windows are excluded from process rules. This is a screening heuristic, not a definitive diagnosis of mechanical degradation.

11. **Pressure-anomaly screening.** A pressure anomaly requires at least 10 consecutive readings above 110% of the median of the first 20 timestamp-ordered good readings for that sensor. Using a fixed initial reference helps prevent a sustained event from raising its own baseline. The pressure sensor is facility-level: this rule cannot identify a specific pipe or prove that a blockage exists.

12. **Leak-like flow-depression scenario.** During the `FAC-001` leak scenario window, generated low-flow readings are assigned round-robin across that facility's pump flow sensors. This does not create synchronized inlet/outlet boundary measurements or an independent mass-balance observation. Detection therefore reports a multi-sensor, facility-level flow-depression proxy rather than a confirmed physical leak. Concurrent pump-level alarms are suppressed in overlapping proxy windows to avoid unsupported per-pump attribution.

## 5. Modeled Flow-Balance Checks

13. **Balance equation and tolerance.** The validator calculates the flow-balance residual as:

    `residual_lps = sum(inlet flows in L/s) - sum(outlet flows in L/s) - tank volume change in L / interval duration in seconds`

    An absolute residual of no more than **8 L/s** is accepted. This is a declared screening tolerance, not a claim about instrument accuracy.

14. **Modeled operating points.** The generated `flow_balances.csv` contains three modeled steady-state operating points per Facility, nine intervals in total. These records are separate from generated telemetry and are not measured boundary flows.

15. **Capacity and throughput assumptions.** For each Facility, inlet and outlet capacities are the sums of `nominal_flow_lps` for the corresponding pumps, grouped using inlet/outlet roles in Sensor metadata. For demand factors `0.50`, `0.75`, and `1.00`, common throughput is calculated as:

    `throughput = min(inlet capacity, outlet capacity) * demand_factor`

    Throughput is apportioned among the pumps on each side in proportion to their nominal capacities.

16. **Steady-state assumption and validation.** Each modeled interval assumes zero tank-volume change. The validator cross-checks pump-capacity inputs against the generated Pump and Sensor records, checks modeled flows against the stated calculation, and then evaluates the balance equation. These deterministic model outputs do not establish actual hydraulic conservation or accuracy in a real network.

## 6. Interpretation and Non-Goals

- The generator creates reproducible synthetic data; reproducibility of generated files does not imply that the data represents real plant behaviour.
- The pump curve and affinity-law relationships are simplified approximations, not a calibrated physical model.
- Scenario labels are for evaluation only. Proxy alarms do not establish a particular physical fault or localize it to an individual component.
- Flow-balance intervals are modeled operating points, not synchronized telemetry measurements or independent evidence of conservation.
- Thresholds are illustrative. The prototype is not safety-certified and must not be used to control real equipment or make operational safety decisions.

## Summary

IndustrialPulse AI uses deterministic synthetic data, simplified pump equations, rule-based detection, and modeled flow-balance checks to demonstrate an end-to-end monitoring workflow. Its outputs should be interpreted as prototype estimates and scenario-screening results—not as validated hydraulic predictions, confirmed fault diagnoses, or safety recommendations.
