# SESC Hybrid DevV0.x — FREEZE 2026-11-04

Freeze name: **SESC Hybrid DevV0.x**

## Firmware basis
- Repository: ZachWay9bot/temp2
- Firmware source parent commit: `8c73d82ddd53a09b5f7896b446624e0aa082fdfe`
- Build ID: `G30D-R3I23-HS3-HF4SL1`
- Architecture: HS3 platform + R3I15HF4 sensorless semantics
- Sensorless core files are pinned to the exact HF4 hashes in CI.
- Hall / Sensorless switch remains present through `mc_conf.foc_sensor_mode`.
- Hall path remains HS3 Hall-FOC.
- Sensorless path remains HF4 pushstart / FO76 observer.
- HS4 rearm experiment is NOT part of this freeze.
- R3I23 startup torque limiter remains present as dead helper code but is NOT wired into the sensorless throttle path.
- HS3 hard 18 V dashboard gate fix remains active.
- IoT/VESC UART behavior remains unchanged.

## Validated build facts
- CI run: 41742537084 — SUCCESS
- BIN SHA256: `037b6567ecab9db909dcd06a0b389b62c098166d4fc8c2475fd8d04a0dc613ff`
- BIN file size: 92068 bytes
- Linker flash use: 92064 bytes
- Static RAM: 20380 / 20480 bytes
- Actual g30p APP flash region: 0x08001000 .. 0x0801DFFF, 0x1D000 = 118784 bytes
- Known CI cleanup item: flash limit check must use 118784 bytes, not 126976.

## Bench diagnostic freeze
Guided test log:
- `GUIDED_SENSORLESS_20261104_143412.log`
- `GUIDED_SENSORLESS_20261104_143412_samples.csv`

Observed:
- Runs 1 and 2 completed stable observer takeover.
- Run 3 produced one fallback while throttle remained active.
- Failure occurred around `last_erpm=-5009`, therefore not at the 64 dpp speed threshold.
- Immediately before/at failure:
  - observer `valid` dropped 1 -> 0
  - `good1k` dropped 200 -> 0
  - `clamp_low` incremented 0 -> 1
  - `fallbacks` incremented 0 -> 1
  - `flux_pre_uWb min` reached 11671 uWb
- Current best diagnosis: observer validity loss / low-flux clamp is the important failure path; 64 -> 48 speed hysteresis is NOT yet justified by this capture.
- Fallback reason is cleared too quickly by the existing rearm path for the polling logger to retain it reliably.

## DO NOT CHANGE inside this freeze
- FO76 observer model constants
- R/L/lambda
- pushstart entry threshold
- Hall LUT / Hall path
- dashboard Vbus fix
- IoT/VESC UART
- coast-only braking
- flash layout / bootloader / option bytes / RDP

## Next development after this freeze
Do development on a NEW branch.
Priority experiments:
1. latch first fallback reason for diagnostics without changing motor control
2. test observer-valid dropout hysteresis as ONE isolated functional change
3. fix guided logger minVbus summary source
4. correct CI APP flash-size gate to 118784 bytes
5. watchdog only as a separate later change, not mixed into motor-control validation

This file is documentation only. It does not change the frozen motor firmware source.
