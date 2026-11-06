# FREEZE — SESC BMS FINAL READ V1 — 2026-11-06

Canonical freeze ID: **SESC-BMS-FINAL-READ-V1-FREEZE-2026-11-06**

## Firmware identity
- Build ID: `SESC-DRV126-POWERCORE6500-BMS-FINAL-READ-V1`
- CI run: `42136443141` — SUCCESS
- BIN SHA256: `ee163b8d2227f013e42faba6f4b9df5e876ade46919e678088a4f23bac30ec7f`
- Flash-ready ZIP SHA256: `4b8de7bd5d390aeb1cf3f1abb2d419003c0e081de6c685492956467896f34aa6`

## Real hardware validation
Test: `BMS_FINAL_READ_V1_20261106_013407`

Validated:
- USART3/BMS 115200 8N1
- 19/19 semantic read paths passed
- 0x10 length 14, 0x30 length 14, 0x40 length 20
- CRC errors 0
- pack 38.200 V
- cell sum 38.210 V
- pack/cell error 10 mV
- SOC 71%
- remaining/actual 10863/15300 mAh = 71.00%
- TIM1 MOE=0 before and after test

## Frozen conclusions
- BMS responds when stock 10S is connected normally on DC+/DC- plus BMS UART.
- C/CHRG_MOD not needed for normal read telemetry; untouched.
- No normal stock DRV126 ESC20->BMS22 CMD 0x02 current-unlock write identified.
- No invented 19A->40A BMS unlock telegram included.
- Nonzero-current sign of 0x33 remains unverified and is not claimed.

## Bench after freeze
Default bench from this point:
- **EA PSU 27 V**
- Stock G30 battery disconnected unless a future BMS-specific test explicitly reopens it.
- No 4S series pack / no 14S for ordinary bench work.
- The frozen BMS image retains the hard powerstage lock. A later non-BMS build may remove that lock deliberately.

Status: **FROZEN / CANONICAL**
