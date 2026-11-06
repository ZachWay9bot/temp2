# FREEZE — SESC SHUD4+BMS CLONKFREE V1 — 10S BMS HW PASS

**Freeze date:** 2026-11-06

## Canonical freeze name

`SESC-SHUD4BMS-CLONKFREE-V1-10S-BMS-HW-PASS-2026-11-06`

## Firmware identity

- Build ID: `SESC-DRV126-P6500-H14-SHUD4BMS-CLONKFREE-V1`
- BIN SHA256: `df8ef433c322b67ec34ae9c5c8dccdd7b980c685652f1a5beab30a31c0541dbc`
- Branch: `hall14s-shud4-bms-clonkfree-v1-20261106`
- Clonkfree source commit: `28fc01786d13331e273551cb22e0d141c325e9fa`
- Previous 27V true-coast freeze marker: `8572294fda7ba79d94dcfa24bb888e1b6cd9f14e`
- CI run: `42300075314`
- CI artifact: `13543766633`

## Accepted Hall behavior

- Hall forward start: PASS
- SHUD-style zero-current rolling coast hold: PASS
- refQ=0 while rolling in coast
- PWM remains enabled above the SHUD release threshold
- three true-coast re-engage cycles passed at 27V
- physical acceptance: CLONK-FREE
- reverse remains out of scope
- sensorless/observer remains out of scope

## Accepted BMS behavior on stock 10S hardware

Stock 10S battery only, external 4S disconnected.

Observed read-heartbeat run:
- `present=1` throughout
- `live30_len=12`
- `crc_bad=0`
- `pack10=3817`
- `soc=70`
- `current=0` at rest
- TX advanced from 6412 to 6457
- OK advanced from 421 to 466
- timeout counter stayed at 5991 during the observed test window
- therefore 45 new TX and 45 new valid replies were observed with zero new timeouts

Conclusion:
- USART3 BMS hardware path: PASS
- Stock/SHUD read heartbeat: PASS
- Runtime 0x30 reply path: PASS
- CRC: PASS
- COM9/VESC path remained usable

The large historical timeout count is retained as diagnostic history and is not treated as a failure because it did not increase during the accepted test window.

## SHUD4 configuration retained

- phase current: ±55 A
- battery input max: +39 A
- current raising coefficient: 6500
- DPC quadratic coefficient: 110
- no-KERS / coast
- coast-hold threshold: |ERPM| > 500

## BMS architecture retained

- BMS: USART3 on BMS connector
- VESC/IoT: USART1 / COM9
- stock/SHUD read heartbeat only
- startup read 0x10
- runtime read 0x30 at nominal ~105 ms
- no invented BMS write command
- no BMS activity in the 16-kHz FOC/PWM path

## Motor-path invariants

- `mc_tasks.c`
  `1c3f61ad12855960ddf25ea96730328bdfaa4d8653d6f7ec9fe89d2114518c98`
- `r3_2_f1xx_pwm_curr_fdbk.c`
  `14ccd029244f230d5632f18c6c278aa3021976ede8a4513939af068456eee276`

## Memory

- Flash: 98904 / 118784 bytes
- RAM: 20396 / 20480 bytes

## Explicitly NOT part of this freeze

- no ride/flight recorder yet
- no persistent logger
- no 14S+BMS acceptance
- no >19 A BMS unlock proof under real load
- no sensorless changes
- no reverse requirement

## Next development step

Stay on stock 10S.

Add a passive RAM-only ride flight recorder outside the high-frequency motor loop to capture after a real ride:
- peak BMS battery current
- minimum BMS pack voltage
- BMS present / TX / OK / timeout delta / CRC
- time above current thresholds such as 15/18/19/20/25/30 A
- peak phase current / requested current
- max ERPM
- faults

Read it after the ride over COM9. Do not require a laptop during riding.

