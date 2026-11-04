# FREEZE — SESC Hall OK — 2026-11-04

Freeze name: **SESC Hall OK**

## Frozen firmware
- Repository: `ZachWay9bot/temp2`
- Freeze branch: `freeze-sesc-hall-ok-20261104`
- Frozen source commit: `993661043e224279a0ab216cf1c721afb3d9bbb6`
- Build ID: `SESC-HALL-DEVV0.1`
- CI run: `41868352675` — SUCCESS
- Artifact: `G30D_SESC_HALL_DEVV01_COMPILED`
- Artifact ID: `13344595347`
- BIN: `SmartESC_v2_G30D_SESC_HALL_DEVV01_STLINK_APP_0x08001000.bin`
- BIN bytes: 93388
- BIN SHA256: `035d0c4608dd1f49d7ed3dfe8188c64ca48bbc280ef158ac6e906aad4ea3ffa6`
- Flash: 93384 / 118784 bytes
- Static RAM: 20388 / 20480 bytes
- Static RAM reserve: 92 bytes
- FreeRTOS heap allocation: 13312 bytes

## Scope
This freeze marks the G30D Hall-FOC path as the validated baseline.

Required behavior:
- Hall mode supports FWD and REV from standstill.
- Sensorless remains separate and FWD-only.
- Direction reversal while still rolling in the opposite direction must coast first, then permit the requested direction near zero speed.
- Brake policy is Coast, no regenerative braking.
- Stock dashboard throttle remains FWD only.
- VESC Tool FWD/REV commands remain available in Hall mode.

## Hardware validation
Guided Hall validation completed successfully on 2026-11-04 using build `SESC-HALL-DEVV0.1`.

Passed:
1. Hall mode active, live Hall valid, stored LUT valid.
2. FWD from complete standstill.
3. REV from complete standstill.
4. FWD -> REV while wheel still rolling: Coast, no active counter-torque / hard kick.
5. Stock dashboard throttle FWD.
6. Brake while rolling: Coast, no regenerative braking.
7. Five repeated starts without power-cycle: FWD, REV, FWD, REV, FWD.
8. Final state: no current or latched motor fault, Hall reliable, PWM off after release.

Observed final runtime health:
- `fault_now=0x0000`
- `fault_latched=0x0000`
- `vesc_fault=0`
- `DriveSensor=HALL`
- `sensorlessActive=0`
- `Hall reliable=1`
- `Hall err=0/20`
- `heap_free=5544`
- dashboard task stack free = 196 words

Validated stored Hall LUT:
`[255,232,143,186,63,17,103,255]`

The older R2 LUT remains structurally valid but is not substituted for the user's validated stored configuration.

## Hall hardening included
- Live Hall GPIO validity check.
- LUT plausibility validation.
- Hall PWM start blocked when Hall state is invalid.
- 000 / 111 invalid Hall states rejected.
- Multi-bit / skipped Hall transition rejected.
- Hall reliability fault latched until explicit Hall clear/rearm.
- TIM1 MOE immediately disabled on an illegal physical Hall transition.
- Hall FWD/REV direction interlock: opposite-direction request coasts while wheel is still clearly rotating.
- VESC command direction pre-check.
- Stock dashboard FWD direction pre-check.
- Safe Hall electrical-angle reseed after invalid state / recovery.
- Hall rolling-start BEMF preload recomputed from live Hall speed.
- Hall speed-feedback fault does not auto-restart under a held drive command.
- Release/zero command is required before Hall fault rearm.
- Recovered Hall release clears only `MC_SPEED_FDBK`; other fault bits are preserved.
- Read-only `g30_hall` diagnostics included.

## Sensorless preservation
The frozen sensorless observer and pushstart core from **SESC Observer OK** remain byte-identical:
- `g30_fo76_shadow.c`
- `g30_fo76_shadow.h`
- `g30_r3i_pushstart.c`
- `g30_r3i_pushstart.h`

Do not change those files as part of Hall maintenance.

## Remaining deliberately unforced cases
The normal Hall driving path is hardware-validated. These Hall fault-injection cases are code/CI validated but were not deliberately induced on powered hardware:
- Hall connector loss / live 000 or 111 state under drive.
- Physically impossible multi-bit Hall edge while energized.
- Full Hall-fault -> release -> repaired-sensor -> restart cycle.

These are not blockers for the normal Hall freeze.

## Do not change inside this freeze
- Validated Hall LUT/config without a new hardware calibration reason.
- Hall FWD/REV zero-speed behavior.
- Coast-before-direction-reversal behavior.
- Coast/no-regen brake behavior.
- Hall fault latch/release semantics.
- Sensorless observer/pushstart frozen under **SESC Observer OK**.
- IoT/VESC UART.
- Bootloader / app origin / option bytes / RDP.

## Memory constraint
Static RAM reserve is only 92 bytes. Avoid adding global/static allocations without reclaiming memory first.

## Release rule
Any future Hall angle, LUT, direction, recovery, fault-detection, interpolation or startup experiment must branch from this freeze and must not overwrite it.

This freeze is the return point for the validated Hall FWD + REV path.
