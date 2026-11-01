# R3I22 DASH PROTOCOL VALIDATION

Scope: offline validation of the Stock G30D dashboard path on top of the R3I21 firmware candidate.

No motor-core, observer, push-start, VESC UART, IAP, light mapping or runtime dashboard code was changed by R3I22.

## Captured bus facts used as ground truth

20 s passive yellow-wire capture:
- valid frames: 616
- DASH65: 410
- DASH64: 103
- ESC64: 103
- bad CRC: 0

Observed frame forms:
- DASH65 starts: 5A A5 05 21 20 65 00 ...
- DASH64 starts: 5A A5 07 21 20 64 00 ...
- ESC64 starts:  5A A5 06 20 21 64 00 ...

Confirmed routing rule:
- valid DASH CMD64 requests one ESC CMD64 status reply
- valid DASH CMD65 is input/heartbeat and does not request a reply
- no ESC65 reply is added because none is supported by the capture

Known input calibration:
- gas idle: about 66..67
- half gas: about 119..121
- full gas: about 189..190
- brake idle: about 34
- full brake capture: gas about 78..80, brake about 196..198

Runtime thresholds under validation:
- gas begin: 75
- gas full: 190
- brake begin: 45
- brake release: 40
- valid raw maximum: 210
- neutral arm: 200 ms
- stale input: 250 ms
- dashboard drive update: 40 ms

## Automated validation

CI test: ci/test_r3i22_dash_protocol.c

Validated:
1. Exact captured class ratio: 410 CMD65 / 103 CMD64 / 103 ESC64.
2. CMD65 never creates an ESC64 reply.
3. CMD64 creates exactly one modeled ESC64 reply.
4. Startup with throttle held cannot arm drive.
5. At least 200 ms valid neutral is required before dashboard drive.
6. Gas threshold edges 75/76 behave as intended.
7. Brake threshold 45 overrides throttle and produces coast.
8. Brake never requests regenerative torque in the dashboard logic.
9. Brake release does not re-arm without a fresh neutral period.
10. More than 250 ms stale input coasts an active dashboard drive.
11. Raw inputs above 210 are rejected and coast an active dashboard drive.
12. motor_ok=false never requests torque.
13. Single-bit corruption of every checksummed byte is rejected.
14. A valid frame immediately after a corrupted frame is accepted.
15. Noise and a >10 ms partial-frame gap resynchronize cleanly.
16. Status-frame encoder reproduces the recorded ESC64 example exactly.
17. R3I21 button regressions remain PASS.
18. Existing R3I15HF4 static motor/observer gates remain PASS.

## CI result

Branch: r3i22-dash-protocol-20261101
CI run: 41347411812
Head: 4f4cc564683889431b2c15b2183059951a3a6d39
Result: SUCCESS

R3I22 DASH PROTOCOL SIM: PASS

The compiled firmware remains the unchanged R3I21 runtime candidate:
- Build ID: G30D-R3I21-DASH-BUTTON
- BIN SHA256: d976e5bf5202503cd3c7be2671311368f45dd5fb66aa51267781d3f86c6c9fd6
- Flash: 91704 / 126976 bytes
- RAM: 20380 / 20480 bytes

## Deliberately unresolved

- Stock-dashboard light command/state mapping is NOT inferred from synthetic payload bytes.
- No ACK65/ESC65 is invented.
- Hardware timing and button/light behavior still require the real scooter.
- R3I21 is still the flash candidate until a runtime change is justified.
