# FREEZE — SESC SHUD4+BMS CLONKFREE V1 — 27V TRUE-COAST PASS

**Freeze date:** 2026-11-06

## Canonical freeze name

`SESC-SHUD4BMS-CLONKFREE-V1-27V-TRUECOAST-PASS-2026-11-06`

## Firmware

- Build ID: `SESC-DRV126-P6500-H14-SHUD4BMS-CLONKFREE-V1`
- BIN SHA256: `df8ef433c322b67ec34ae9c5c8dccdd7b980c685652f1a5beab30a31c0541dbc`
- Branch: `hall14s-shud4-bms-clonkfree-v1-20261106`
- Freeze source commit: `28fc01786d13331e273551cb22e0d141c325e9fa`
- CI run: `42300075314`
- Artifact: `13543766633`

## Accepted hardware behavior at 27 V

- Hall forward start: PASS
- SHUD-style zero-current rolling coast hold: PASS
- PWM remains enabled while rolling above the SHUD threshold
- `refQ=0` during coast
- no faults during three true-coast re-engage cycles
- meaningful coast/deceleration before re-engage was demonstrated
- re-engage occurred without PWM restart
- physical user acceptance: CLONK-FREE

## SHUD4 behavior retained

- phase current: ±55 A
- battery input limit: +39 A
- current raising coefficient: 6500
- DPC quadratic coefficient: 110
- no-KERS / coast
- coast-hold threshold: |ERPM| > 500

## BMS architecture retained

- BMS on USART3 / BMS connector
- VESC/IoT remains USART1 / COM9
- stock/SHUD read heartbeat only
- startup read 0x10
- runtime read 0x30 at ~105 ms
- no invented BMS writes
- no BMS work in 16-kHz FOC/PWM

## Motor-path invariants

Fast FOC and PWM/ADC files remain byte-identical to the hardware-proven Hall baseline:

- `mc_tasks.c`
  `1c3f61ad12855960ddf25ea96730328bdfaa4d8653d6f7ec9fe89d2114518c98`
- `r3_2_f1xx_pwm_curr_fdbk.c`
  `14ccd029244f230d5632f18c6c278aa3021976ede8a4513939af068456eee276`

## Memory

- Flash: 98904 / 118784 bytes
- RAM: 20396 / 20480 bytes

## Do not regress

- Do not restore PWM-off during rolling zero-current coast above the SHUD threshold.
- Do not reset PI/Vqd during a rolling re-engage.
- Do not change the clonk-free Hall coast-hold unless a hardware regression proves it necessary.
- Do not touch sensorless/observer yet.
- Do not move BMS activity into the high-frequency motor loop.
- Do not add reverse as a release requirement.

## Remaining validation

This freeze does **not** claim full BMS/14S hardware acceptance yet.

Next:
1. 10S stock-BMS read-only heartbeat hardware proof.
2. 14S Hall+BMS forward regression.
3. real-load verification that the stock-BMS no-communication current fallback is no longer limiting the system.
4. final full Hall14S+BMS performance freeze.

