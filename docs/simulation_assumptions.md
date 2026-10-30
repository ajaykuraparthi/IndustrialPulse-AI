# Simulation assumptions
1. All data is synthetic; no operational plant data is used.
2. Flow is L/s, pressure is kPa, tank volume is liters, and timestamps are UTC.
3. The pump curve is approximated by H(Q) = H0 - k Q^2.
4. Pump speed changes use affinity-law approximations Q2/Q1 ≈ N2/N1 and H2/H1 ≈ (N2/N1)^2.
5. The simulation endpoint currently estimates pump-only output; it does not solve the entire network's hydraulic operating point.
6. Leak/blockage labels are documented scenario labels. Detection rules are independent of ground-truth files.
7. Sensor faults affect measurement quality and must not automatically be treated as proof of a process fault.
8. Thresholds are illustrative and must be calibrated and safety-reviewed before any real-world use.
