# SESC DRV126 POWERCORE6500 FINAL V1

Date: 2026-11-05

## Target architecture
SmartESC/SESC remains the firmware and VESC Tool keeps the existing selectable modes:
- HALL = Hall Only
- SENSORLESS = Sensorless Only

There is no automatic Hall/Sensorless hybrid.

Both modes use the same DRV126-derived motor/power core:
- stock current-domain bridge 51575/16384
- stock Clarke
- stock trig/Park
- stock PI-B / PI-C
- stock inverse Park
- stock six-sector SVPWM and sector order
- 1.000 us physical deadtime
- DRV126 current-control cadence 4 kHz
- modified DRV126 current_raising_coefficient = 6500 mA/update

The only deliberate hardware-timing compatibility exception is the retained 16-kHz PWM/current-sampling carrier. The frozen FO76 observer explicitly requires 16 kHz and internally decimates to its 4-kHz model. Moving to the stock ~8-kHz carrier would change the validated Sensorless path.

## Mode behavior
### HALL ONLY
Hall angle/speed -> DRV126 PowerCore -> MOSFET bridge.

The fast Hall GPIO validity guard remains active.

### SENSORLESS ONLY
Frozen R3I/FO76 pushstart and observer -> observer angle/speed -> the same DRV126 PowerCore -> MOSFET bridge.

The observer receives the actually applied previous DRV126 PWM compare vector for voltage reconstruction. Sensorless startup preload now seeds the DRV126 PI that owns PWM.

## coeff 6500
G30 current scale = 374.679722667 counts/A.

6500 mA = 2435.418 counts, implemented as 2435 counts per DRV126 4-kHz controller update.

55 A from zero therefore requires 9 controller updates = 2.25 ms.

The slew is symmetric for rising, falling and sign reversal, and occurs before the stock-domain current PI.

## Frozen Sensorless behavior retained
- R_eff = 583 mOhm
- L_eff = 640 uH
- lambda_eff = 24200 uWb
- DT K = -22528 Q15
- pushstart threshold = 64 dpp
- 800 ms 1-A catch hold
- following 1000 ms current ramp
- observer fallback -> Coast
- Sensorless reverse remains intentionally out of scope
- coast/no regen policy retained

## Build
- Branch: `sesc-drv126-powercore6500-final-v1-20261105`
- CI head: `cd2cb92dedaae282df885b7e72702c7ea33e0b66`
- CI run: `42039711449` SUCCESS
- Artifact ID: `13420237650`
- Build ID: `SESC-DRV126-POWERCORE6500-FINAL-V1`
- BIN SHA256: `8ceb5348bb53c34b8992025d188d20ebbc2e14a355f92e405d4b309f0f108b80`
- Flash: 97656 / 118784 bytes
- RAM: 20412 / 20480 bytes
- Static RAM reserve: 68 bytes

## Offline acceptance
`SESC_DRV126_POWERCORE6500_FINAL_V1_OFFLINE_SUITE=PASS`

Covered:
- exact coeff6500 scaling and 4-kHz placement
- 55-A ramp timing and sign reversal
- shared Hall/Sensorless DRV126 power core
- mode-specific Hall safety guard
- actual DRV126 PWM feedback to FO76
- DRV126 sensorless startup preload
- 16-kHz FO76 contract
- no Hybrid mode
- stock DRV126 math core
- 1-us deadtime
- unchanged pushstart hash
- unchanged observer physical model
- fallback/coast/no-regen
- configured current/battery/FW limits

This is the single target image for hardware validation. No further staged firmware is required unless hardware evidence exposes a real defect.
