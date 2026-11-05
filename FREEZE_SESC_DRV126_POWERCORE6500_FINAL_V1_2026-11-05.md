# FREEZE SESC DRV126 POWERCORE6500 FINAL V1

Freeze date: 2026-11-05

Canonical freeze name:

`SESC-DRV126-POWERCORE6500-FINAL-V1-2026-11-05`

## Git / CI identity

- Development branch: `sesc-drv126-powercore6500-final-v1-20261105`
- Development head / source commit: `bb76be300f082f0ffded43d76a318db3aa2d669c`
- Freeze branch: `freeze-sesc-drv126-powercore6500-final-v1-20261105`
- CI workflow: `.github/workflows/drv126-powercore6500-final-v1.yml`
- CI run: `42040326759` — SUCCESS
- CI artifact ID: `13421975037`
- GitHub artifact SHA256: `9e94c60e0ad3eac127188c2b0f48d5123b56ef0ff9fd9e05291a90b531fd3f74`

## Firmware identity

- Build ID: `SESC-DRV126-POWERCORE6500-FINAL-V1`
- BIN: `SmartESC_v2_G30D_SESC_DRV126_POWERCORE6500_FINAL_V1_STLINK_APP_0x08001000.bin`
- BIN SHA256: `8ceb5348bb53c34b8992025d188d20ebbc2e14a355f92e405d4b309f0f108b80`
- Exact source TGZ SHA256: `b20da05b01a5f80dce8a005404bc31fe53a0e6f7c74d694f788ba5a085410aa3`
- Apply-script SHA256: `ee1f5145aafc8e612f5eacf0abfcadca11e0ecf07d3931acb04f1cbca4a4425c`
- Offline-test-script SHA256: `ca45c44c21767aa46646815a81083f8a99693ddb480b574392981ae929b8f864`

## Memory

- Flash: `97656 / 118784 B`
- RAM: `20412 / 20480 B`
- Static RAM reserve: `68 B`

## Frozen architecture

This freeze is the normal SmartESC/SESC firmware with the already-developed sensor paths retained.

### Sensor selection

VESC Tool remains authoritative:

- `HALL` = Hall-only path
- `SENSORLESS` = FO76/R3I sensorless-only path
- No automatic Hall/Sensorless hybrid switching is introduced by this freeze.

### Shared motor / power core

Both selectable sensor modes feed the same DRV126-derived motor/power core:

- stock-domain current bridge
- Clarke
- Park
- stock-derived q/d current PI
- inverse Park
- 6-sector SVPWM
- DRV126-derived power-stage control
- 1 us physical deadtime
- DRV126 current-raising coefficient changed to `6500 mA/update`

The coefficient is applied at the 4-kHz DRV126 current-controller update rate.

For the measured G30 current conversion this is:

- current factor: about `374.6797 counts/A`
- 6500 mA step: `2435 MC counts`
- 0 -> 55 A ideal slew: 9 controller updates = `2.25 ms`

### Hall mode

Hall angle/speed remain supplied by the frozen SESC Hall path.
The DRV126-derived motor/power core performs the actual current regulation and bridge drive.

### Sensorless mode

The frozen FO76/R3I observer remains the sensorless angle/speed source.
The observer receives the actual previously applied DRV126 PWM vector.
Sensorless push-start, preload/hold/ramp, observer constants and fallback/coast behavior are retained.

The sensorless observer contract remains based on the established 16-kHz FOC/PWM timing while the DRV126 current regulator updates at 4 kHz.

## Offline verification

CI offline suite result:

`SESC_DRV126_POWERCORE6500_FINAL_V1_OFFLINE_SUITE=PASS`

Confirmed gates include:

- build identity
- coeff=6500 scaling
- coeff update position after 4-kHz divider
- 55-A ramp arithmetic
- current sign reversal
- common DRV126 power core for Hall and Sensorless
- mode-specific Hall guard
- actual DRV126 PWM feedback into sensorless observer
- sensorless preload / hold / ramp
- 16-kHz observer / 4-kHz DRV126 contract
- no hybrid mode change
- DRV126 stock math core
- 1-us deadtime
- frozen push-start hash
- observer physical-model constants
- sensorless fallback to Coast
- SESC limits / FW / Coast policy
- mode state table

## Hardware status at freeze

The component paths are based on previously hardware-validated Hall, observer, and DRV126 takeover work.

Important: this exact combined `POWERCORE6500 FINAL V1` image is frozen before its first full hardware acceptance run. Therefore the freeze means:

- source/build identity is immutable
- offline integration checks are complete
- future hardware test results must be recorded against this exact BIN hash
- any firmware modification after this point requires a new branch/version and must not overwrite this freeze

## Safety / recovery

- Application start: `0x08001000`
- No Mass Erase
- No Option Byte modification
- No RDP modification
- Keep known-good Hall / Observer / prior FINAL V1 / Stock recovery images available

## Do not change in this freeze

Do not modify:

- Hall algorithm / LUT behavior
- FO76 observer model
- sensor-mode selection semantics
- DRV126 current/Park/PI/SVPWM core
- coefficient 6500
- current-controller cadence
- PWM/deadtime contract
- Coast/no-regen policy
- communication / Dash / VESC Tool mode-selection behavior

Any such change starts a new development line.
