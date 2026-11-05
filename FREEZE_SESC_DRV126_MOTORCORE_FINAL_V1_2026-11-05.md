# FREEZE SESC DRV126 MOTORCORE FINAL V1

Freeze date: 2026-11-05

Canonical freeze:
`SESC-DRV126-MOTORCORE-FINAL-V1-2026-11-05`

## Source and build
- Development branch: `sesc-drv126-motorcore-final-v1-20261105`
- Freeze source commit: `0b98cb0b47c72c3fcb3bf39bf91a7618d0ce5bbe`
- CI run: `41944658209` SUCCESS
- Artifact ID: `13378650890`
- Build ID: `SESC-DRV126-MOTORCORE-FINAL-V1`
- BIN: `SmartESC_v2_G30D_SESC_DRV126_FINAL_V1_STLINK_APP_0x08001000.bin`
- BIN SHA256: `a45c3c4cc7711bc962622e52cdcb386c27da57e62003694aaf212996939d4113`
- Flash: 97456 / 118784 bytes
- RAM: 20404 / 20480 bytes
- Static RAM reserve: 76 bytes

## Production architecture
### HALL
Hall mode automatically uses the proven DRV126 motor-control core:
1. existing MCSDK current acquisition
2. exact MCSDK->DRV126 current-domain bridge
3. DRV126 Clarke
4. DRV126 Park / stock trig LUT
5. stock PI-B / PI-C integer control
6. stock inverse Park
7. stock six-sector SVPWM
8. stock sector used directly
9. scaled onto the validated SESC 2000-count carrier
10. existing MCSDK sector-aware ADC sampling writer on every 16-kHz ISR

Control cadence remains DRV126 4 kHz while PWM/current acquisition remains 16 kHz.

No RAM arm command or takeover test mode remains.

### SENSORLESS
Sensorless selection remains on the frozen SESC/FO76 observer/start/control path.
The final DRV126 patch does not modify:
- `g30_fo76_shadow.c`
- `g30_fo76_shadow.h`
- `g30_r3i_pushstart.c`
- `g30_r3i_pushstart.h`

Their frozen SHA256 hashes are checked by CI.

## Supervisory integration restored
Unlike the R1.2 bench takeover, FINAL V1 publishes live values back into:
- `FOCVars.Iab`
- `FOCVars.Ialphabeta`
- `FOCVars.Iqd`
- `FOCVars.Vqd`
- `FOCVars.Valphabeta`

and calls `FW_DataProcess()` in Hall mode.

Therefore the existing supervisory functions continue to see live data:
- battery-current limiting
- field weakening
- motor power/current telemetry
- VESC current/voltage reporting

## Start/stop behavior
- DRV126 integrators reset on normal stop / FOC clear.
- Hall rolling restart preloads DRV126 q/d integrators from the existing proven Hall BEMF voltage preload.
- Sensorless preload remains unchanged.

## Safety behavior
- live Hall raw 000/111 rejected in every current ISR
- invalid Hall LUT entry rejected
- unreliable Hall state immediately removes PWM
- existing medium-frequency Hall fault handling remains authoritative
- direction reversal while wheel rotates opposite remains Coast-first
- brake policy remains Coast, no regen
- existing all-phase software OCP remains enabled
- hardware/MCSDK fault processing unchanged

## Removed experimental restrictions
The R1/R1.2 fixed 3-A q-current and test rail guards are gone.
Normal configured SESC phase-current limits are authoritative.

The exact stock SVPWM was exhaustively checked over the PI output space:
- raw compare range: 40..3960 / 4000
- maximum active span: 3920
- all six sectors covered
- boundary ties retain the stock sector instead of forcing the experimental neutral vector

## Offline scenario suite
CI `DRV126_FINAL_V1_OFFLINE_SUITE=PASS` covers:
- complete signed int16 current bridge domain
- 0 A, 1 A, 2 A, 3 A, 30 A, 40 A, 45 A, 60 A scaling
- FWD/REV numerical symmetry
- 250,000 randomized PI cases
- transform 32-bit overflow bounds
- 4-kHz control / 16-kHz sample commit cadence
- Hall 0 / Hall 7 / unreliable Hall states
- automatic Hall ownership
- no test arm surface
- configured current-limit plumbing
- full FOCVars / FW telemetry
- Hall preload and stop reset
- frozen sensorless hashes
- no-regeneration policy

## Hardware evidence inherited
R1.2 hardware log:
`DRV126_R12_LOADSYM_20261105_012054.log`
SHA256:
`daa826da1b99e81c9f26e34be3052384e3e8d314ed20619d4e96bff94f1005e5`

Observed on the 24-V / dual-halogen bench:
- FWD 1 A: barely/twitch
- FWD 2 A: clean rotation
- FWD 3 A: clean rotation
- REV 1 A: barely/twitch
- REV 2 A: clean rotation
- REV 3 A: clean rotation
- no motor fault
- no OCP
- no DRV takeover trip
- timing clean

R0.3 hardware comparison previously established:
- zero phase-order mismatches
- <=13 / 2000 compare-count difference between DRV126 reconstructed PWM and live SESC PWM

## Deliberate non-changes
FINAL V1 does NOT switch to the stock 8-kHz TIM1 carrier.
The proven 16-kHz SESC hardware/ADC layer is retained because changing the
carrier would add a new timer/ADC variable without solving a demonstrated fault.

FINAL V1 does NOT add the alternate staging-firmware +/-15-degree speed angle
correction. The active DRV126 path does not contain that correction and R1.2
already proved clean FWD/REV rotation from the existing Hall angle source.

## Validation boundary
Software arithmetic, timing architecture, current limiting integration and the
low-current real-hardware motor path are validated as above.

A 36-V battery / full-current road test of this exact FINAL V1 image is not
claimed by offline analysis. That is a physical validation boundary, not a
reason for another diagnostic firmware branch.

This freeze is the production motor-core baseline. Future work should branch
from this freeze only for a genuinely new feature, not for another DRV126
takeover experiment.
