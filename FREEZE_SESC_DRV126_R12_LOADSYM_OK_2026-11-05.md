# FREEZE SESC DRV126 MOTORCORE R1.2 LOAD/SYMMETRY OK

Freeze date: 2026-11-05

Canonical name:
`SESC-DRV126-MOTORCORE-R1.2-LOADSYM-OK-2026-11-05`

## Source / CI
- Base branch: `sesc-drv126-motorcore-r12-loadsym-20261105`
- Freeze source commit: `1c56dcb4ffac28423bac6e1484f42f0c533416b1`
- CI run: `41940016704` SUCCESS
- Artifact ID: `13376705201`
- Build ID: `SESC-DRV126-MOTORCORE-R1.2-LOADSYM`
- BIN SHA256: `cb0e74fdaa787e479c339b1392e739b135520bd2e146236d5ffd452b0a21272a`
- Guided package SHA256: `0c78a7c4c3ff29d7c47c1a84107af557dbc25ef90067b98aa962c5451fc033ee`
- Exact source package SHA256: `8c8592ec4dce5e4c6f7133a1746d0178cc41d57a87ce7f692452617acb86530f`

## Hardware evidence
Hardware log:
`DRV126_R12_LOADSYM_20261105_012054.log`
SHA256:
`daa826da1b99e81c9f26e34be3052384e3e8d314ed20619d4e96bff94f1005e5`

Bench:
- 24 V supply path with 2x 12 V / 20 W halogen series limiter
- wheel free
- Hall mode
- DRV126 current controller 4 kHz
- existing SESC carrier / ADC commit 16 kHz
- no 36 V battery

Observed physical results:
- FWD 1.0 A: barely / twitch
- FWD 2.0 A: clean rotation
- FWD 3.0 A: clean rotation
- REV 1.0 A: barely / twitch
- REV 2.0 A: clean rotation
- REV 3.0 A: clean rotation

Functional direction symmetry is therefore validated from 2 A upward on this bench.

## Runtime safety result
Across all six stages:
- fault_now = 0
- no latched motor fault
- R1.2 trip = 0
- OCP cycNow = 0
- q/d PI saturation counters = 0
- minimum Vbus = 26133 mV
- R1.2 timing max = 1112 / 4000 cycles
- final capture complete

## Stage summaries
| Stage | Physical | qref max | Iq max | Id max | ERPM summary | R12 cycles max |
|---|---|---:|---:|---:|---:|---:|
| FWD 1 A | barely | 1178 | 730 | 118 | -108..0 | 1106 |
| FWD 2 A | clean | 2358 | 1463 | 386 | -1932..0 | 1098 |
| FWD 3 A | clean | 3539 | 1379 | 1200 | -4500..0 | 1101 |
| REV 1 A | barely | 1177 | 766 | 100 | 0..0 | 1107 |
| REV 2 A | clean | 2357 | 1302 | 544 | 0..1752 | 1102 |
| REV 3 A | clean | 3538 | 1458 | 838 | 0..4332 | 1112 |

Note: physical movement flags are authoritative for the load/symmetry gate. The log also contains faster live ERPM samples outside the compact stage maxima.

## What this freeze proves
- first DRV126 takeover path that physically rotates the G30 motor cleanly in both FWD and REV
- R1.1 timing fix remains valid
- direction/sign handling is no longer asymmetric
- the original DRV126 Clarke/Park/PI/inverse-Park/SVPWM path is functionally capable of driving the real hardware
- 1 A is below the useful free-wheel breakout threshold on this bench
- 2 A and 3 A are clean in both directions

## Still NOT final
This freeze does NOT claim:
- native stock DRV126 TIM1 timing
- native stock 8 kHz PWM carrier
- battery / 36 V validation
- full current-loop fidelity at 3 A

At 3 A command the sampled Iq does not reach the full q-reference and Id can become substantial. This is the next audit target before changing the timer carrier.

## Next target
Investigate current-loop fidelity / exact stock PI and current-domain behavior under load while keeping the proven R1.2 timer infrastructure unchanged.

Do NOT replace this freeze with R1.1. R1.1 was timing-safe but did not physically rotate cleanly at the tested 1 A level.
