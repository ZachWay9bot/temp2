# R3I24-LIGHT01-TEST (3 Nov 2026) - isolated experimental variant

Based exactly on branch `r3i24-dash-mode-safe-20261102` commit `793c2dfa64f5acdf5af9ab90e2be5bb4ff957c8d`.
Frozen source and motor path are not modified; this branch is separate.

## One behavioral modification
In copied HF4 Dash link source (`ci/hf4_dash_link_r1/g30_dash_link.c`),
change only CMD64 byte `status[2]` from `light?100:0` to `light?1:0`.
The native checksum is recomputed by the unchanged frame builder.

No change to button event detection, single/double/long press, power control,
Dashboard gas/brake, FOC, observer, IoT VESC COM9, BMS, bootloader, flash origin,
or output GPIOs. Build marker and CI audit are updated only for traceability.

## Evidence / limits
R3I24 real C3 test (2026-11-03) captured a lasting switch from ESC
`light=100` to `light=0` while the original headlamp physically remained lit.
Stock DRV126 controls the same lamp correctly.
Independent VESC G30 scripts commonly encode CMD64 `light` as 0/1;
these do not prove the exact stock DRV126 byte semantics.
This candidate is a hypothesis test, **not** a confirmed light fix.

Expected frame with mode=4, battery=89:
- light OFF: `5A A5 06 20 21 64 00 04 59 00 00 00 00 F7 FE`
- light ON: `5A A5 06 20 21 64 00 04 59 01 00 00 00 F6 FE`

## Test discipline
Wheel clear, motor torque disabled (no gas). Test only 1x button -> ON,
second 1x -> OFF and passive ESP32-C3 Yellowwire capture. If the lamp still
stays on while CMD64=0, this hypothesis is falsified; next step is to compare
the original stock frame sequence, not adjust pins or invent a telegram.

**Do not treat a CI success as a hardware validation.**
