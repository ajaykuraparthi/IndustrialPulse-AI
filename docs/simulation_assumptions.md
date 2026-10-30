# Simulation assumptions
1. All data is synthetic; no operational plant data is used.
2. Flow is L/s, pressure is kPa, tank volume is liters, and timestamps are UTC.
3. The pump curve is approximated by H(Q) = H0 - k Q^2.
4. Pump speed changes use affinity-law approximations Q2/Q1 ≈ N2/N1 and H2/H1 ≈ (N2/N1)^2.
5. The simulation endpoint currently estimates pump-only output; it does not solve the entire network's hydraulic operating point.
6. Leak/blockage labels are documented scenario labels. Detection rules are independent of ground-truth files. Ground-truth `component_id` is a legacy target-ID field whose namespace depends on `issue_type`.
7. Sensor faults affect measurement quality and must not automatically be treated as proof of a process fault.
8. Thresholds are illustrative and must be calibrated and safety-reviewed before any real-world use.
9. Pump degradation is screened using sustained flow below 75% of the pump's nominal flow; `suspect` telemetry is excluded from process rules.
10. Pressure anomalies require at least 10 consecutive readings above 110% of the median of the first 20 timestamp-ordered readings for that sensor. This fixed initial reference avoids letting a sustained event normalize its own baseline. The pressure sensor is facility-level; it does not identify a pipe or prove blockage.
11. The leak scenario reduces all FAC-001 pump flow measurements together and provides no independent mass-balance measurement. Detection is therefore a multi-pump facility flow-depression proxy, not a physical leak conclusion. Concurrent pump-level alarms are represented by this aggregate proxy to avoid unsupported per-pump attribution.
