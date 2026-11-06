# INVALIDATION / SUPERSEDE NOTICE — R3 TRUE-COAST TEST

Date: 2026-11-06

The previous host acceptance labelled:

`SESC-SHUD4BMS-CLONKFREE-V1-27V-TRUECOAST-PASS-2026-11-06`

must **not** be used as proof of true mechanical coasting.

## Reason

The R3 host test's zero-current coast loop sent both:

- current command = 0
- RPM command = 0

The RPM=0 command can invoke active speed control / braking and therefore can
artificially create the observed speed decay.

The required ~35% speed drop was therefore not a valid proof of passive coast.

## What remains valid

- Firmware identity and CI build integrity.
- Hall forward operation.
- BMS read heartbeat observations.
- PWM stayed enabled while rolling with refQ reported as zero.
- No fault during the tested sequences.

## What is invalidated

- The claim that R3 demonstrated true passive/freewheel coast.
- The claim that the observed R3 speed decay was natural coast.
- Any freeze name containing TRUECOAST-PASS as an acceptance of passive coast.

## Replacement test requirement

R4 must:
- never send RPM=0 during coast or cleanup,
- use only repeated current=0 commands during coast,
- not require an artificial percentage speed drop,
- hold current=0 for a fixed freewheel interval,
- verify refQ=0 / fault=0 / PWM continuity,
- then re-engage from whatever real speed remains above the SHUD threshold,
- require physical user confirmation that the wheel genuinely freewheeled rather than being actively slowed.

