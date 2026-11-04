# FREEZE — SESC Motorpath V0.3 Pre-Battery — 2026-11-04

Freeze name: **SESC Motorpath V0.3 Pre-Battery**

This is an explicit **pre-36V-battery return point**, not the final "Motorpath OK" freeze.

## Frozen firmware
- Repository: `ZachWay9bot/temp2`
- Freeze branch: `freeze-sesc-motorpath-v03-prebattery-20261104`
- Frozen source commit: `060bb17190a799e5a6741bef0487a6d1427a08cd`
- Build ID: `SESC-MOTORPATH-AUDIT-V0.3`
- Enforced CI workflow: `.github/workflows/motorpath-v03-enforced.yml`
- CI run: `41903914079` — SUCCESS
- Artifact: `G30D_SESC_MOTORPATH_AUDIT_V03_COMPILED`
- Artifact ID: `13359337406`
- BIN: `SmartESC_v2_G30D_SESC_MOTORPATH_AUDIT_V03_STLINK_APP_0x08001000.bin`
- BIN SHA256: `000884690488ed4e4411686ec7e18a003e4e1b6357354512c90cd9d9c55a3bf8`
- Flash: 95440 / 118784 bytes
- Static RAM: 20388 / 20480 bytes
- Static RAM reserve: 92 bytes

## Frozen upstream subpaths
- **SESC Observer OK** remains the sensorless observer/pushstart baseline.
- **SESC Hall OK** remains the Hall FWD/REV baseline.
- Motorpath V0.3 does not intentionally retune Hall or observer logic.

## Motorpath V0.3 safety fixes
1. Software OCP phase-C reconstruction is compared in wide `int32_t` arithmetic before any legacy `int16_t` storage narrowing.
2. Reconstructed phase-C legacy field is saturated instead of wrapping.
3. Absolute-current/OCP threshold is saturated to `INT16_MAX`; a legal VESC current setting above the representable G30 threshold can no longer wrap negative and disable software OCP.
4. 60 A configured OCP remains approximately 22480 counts / 59.997 A.
5. Torque PI output limits use torque units, not `q * SP_KIDIV`.
6. G30 torque path forces no active braking/regen even if an imported `mc_conf.s_pid_allow_braking` bit is set.
7. Dormant temperature derating endpoint typo was corrected to `temp_cut_end`.
8. No Current-PI Kp/Ki retune.
9. No PWM frequency change.
10. No physical deadtime change.
11. No software deadtime compensation enabled.

## PWM / deadtime baseline
- FOC/PWM: 16 kHz.
- TIM1: PSC=0, ARR=2000, RCR=1.
- BDTR DTG=32.
- TIM1 deadtime timebase uses CKD=DIV2, so the physical deadtime remains **1.000 us**.
- Software DT compensation remains OFF.

## Hardware validation on 24 V PSU + 2x12 V/20 W halogen series
Guided log: `MOTORPATH_V03_20261104_213128.log`

Final summary:
- `PASS`
- Build: `SESC-MOTORPATH-AUDIT-V0.3`
- Hall mode.
- `fault_now=0x0000`
- `fault_latched=0x0000`
- minimum Vbus: **18.855 V**
- maximum observed modulation: **0.975**
- ADC sample validation: **23 valid / 0 mismatch**
- high-modulation valid samples: **4**
- minimum real configured sample margin: **422 ns**
- maximum observed FOC load: **89 %**
- maximum |Iq|: **4.048 A**
- maximum |Iq error|: **2.482 A**
- maximum software OCP counter: **0**
- current offsets: **32698 / 32897 / 32908**
- DTG: **32**
- software deadtime compensation: **0**

Stage evidence:
- REV 3 A: TIME, Vmin 21.975 V, max modulation 0.975, 6/0 sample validation, FOC max 83 %.
- FWD 6 A short: intentionally ended by SUPPLY_LIMIT at Vmin 18.855 V; 2/0 sample validation, FOC max 82 %.
- FWD 3 A high-mod: HIGHMOD_CAPTURED, Vmin 21.412 V, modulation 0.950, 9/0 samples, 3 high-mod valid samples, FOC max 89 %.
- CENTER and BEFORE ADC-trigger paths were hardware observed and matched expected CCR4 values.
- AFTER / MIRROR paths were not forced in this test.

## Interpretation frozen with this point
- The 24 V / halogen bench is supply-limited above the low-current tests.
- The observed high-speed Iq tracking error occurs while the voltage command approaches the configured modulation/voltage limit; it is not currently evidence of a bad Current-PI.
- The common motor-control chain is validated at low current and high modulation:
  current sensing -> Clarke/Park -> Iq/Id PI -> circle limitation -> inverse Park -> SVPWM -> adaptive CCR4 current sampling -> TIM1 gate drive.
- Do not retune Current-PI, deadtime or SVPWM from this freeze without new evidence.

## Remaining open items before final Motorpath OK
1. **36 V battery validation is still pending.**
2. Performance above the supply-limited 6 A bench point is not yet hardware-validated.
3. First battery test should stay conservative:
   - battery/input current max about 15 A,
   - motor current max/min +30/-30 A,
   - absolute current 60 A,
   - max duty 0.95,
   - field weakening 0 A,
   - free wheel / no road load,
   - staged phase-current test 3 A -> 6 A -> 12 A -> 18 A.
4. G30 MCSDK temperature path currently uses a virtual temperature sensor; no proven real MOSFET/heatsink overtemperature cutoff is part of this freeze.
5. TIM1 BKIN / hardware break is currently disabled and must not be enabled without confirmed G30 board signal source and polarity.
6. Static RAM reserve is only 92 bytes.
7. Worst observed FOC load is 89 %, so realtime headroom remains a watch item.

## Do not change inside this freeze
- Observer freeze.
- Hall freeze.
- Current PI gains.
- 16 kHz PWM.
- 1 us physical deadtime.
- ADC sampling algorithm.
- V0.3 OCP hardening.
- G30 Coast/no-regen policy.
- IoT/VESC UART.
- Bootloader / app origin / option bytes / RDP.

## Release rule
Any battery-power, higher-current, PI, deadtime, SVPWM, current-sense, OCP, BKIN or thermal experiment must branch from this freeze and must not overwrite it.

This freeze is the exact return point immediately before the first controlled 36 V battery motorpath test.
