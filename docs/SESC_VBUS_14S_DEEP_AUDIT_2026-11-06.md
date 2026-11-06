# SESC VBUS / 14S DEEP AUDIT — 2026-11-06

Status: **software/static audit complete; 27 V hardware characterization build prepared; no 14S release yet.**

## 1. Scope and references

Audited current SESC/POWERCORE6500 source reconstructed from the hardware-validated BMS FINAL READ V1 lineage, plus:
- Stock DRV126 reference SHA256 `3da93fb2eabfb6c46bf5d652f9317e186326bf1390967f90949eaab6a4b29c9f`.
- SHUD(4) / modified DRV126 reverse-engineering set with 46 patch spans / 143 changed bytes.
- Historical FO76/XBOT G30 voltage-sense reference documenting PA1 V_BAT and nominal 130k/10k divider (ratio 14).
- Real POWERCORE6500 / SPEEDTEL logs at approximately 27 V.

This audit does **not** treat obsolete DeltaESC experimental branches as a voltage-reference source.

## 2. Current SESC PA1 conversion

For G30P:
```c
#define VBUS_ADC_CHANNEL MC_ADC_CHANNEL_1
#define VOLTAGE_DIVIDER_GAIN 3363.5f
#define ADC_GAIN (3.3f / 4095.0f)
#define BATTERY_VOLTAGE_GAIN ((VOLTAGE_DIVIDER_GAIN * ADC_GAIN) * 512.0f)
```

Calculated:
- `BATTERY_VOLTAGE_GAIN = 1387.782564 counts/V`
- unsigned-16 representation ceiling: `65535 / gain = 47.222816 V`
- 12-bit left-aligned maximum (0xFFF0 = 65520): approximately `47.212 V`

The ADC is configured left-aligned. Real 27 V logs are consistent with this model:
- about 27.12 V -> ADC average about 37,643 counts.
- runtime diagnostic already reports `ADC_fullscale=47222mV`.

This is therefore not merely a VESC display-range problem. The present PA1 analog/digital measurement path has no information above roughly 46–47.2 V. The historical G30 reference uses a nominal ratio-14 divider, which gives 46.2 V at 3.3 V ADC full scale; the current SESC gain is an empirical/software calibration in the same physical range.

## 3. Protection consequence

`conf_general_bus_voltage_limit_counts()` correctly saturates requested voltage thresholds to UINT16_MAX before narrowing.

With the current gain:
- requested 8 V UV threshold -> about 11,102 counts.
- requested 56 V OV threshold -> about 77,716 counts and is therefore clipped to 65,535.

Result:
- the software avoids integer wraparound;
- but PA1 cannot discriminate 47.2 V from 56 V or 58.8 V after saturation;
- therefore a configured 56 V over-voltage limit is **not physically enforceable from PA1 alone**.

Low-voltage battery cut remains meaningful because its thresholds (20.4/18.0 V in the accepted configuration) are far below saturation.

## 4. Hall / DRV126 POWERCORE path

The active `g30_drv126_final_power_step()` current loop contains:
- current reconstruction,
- Clarke/Park-equivalent stock-domain transform,
- q/d current PI,
- inverse transform,
- stock-style SVPWM.

The audited function does not consume `VBS_Get...`, `VescToSTM_get_bus_voltage()`, or `BATTERY_VOLTAGE_GAIN`.

Conclusion:
- the inner Hall current-control/PWM loop itself does not require a correct absolute Vbus value;
- high-voltage operation with a saturated PA1 reading is therefore technically compatible with the historical observation that DRV126/SHUD-style Hall control could run above the PA1 sensing range;
- voltage-dependent telemetry, power/current estimates, FW/supervisory behavior and over-voltage protection still become inaccurate above the PA1 ceiling.

This explains historical operation. It is **not** a safety approval for 14S.

## 5. FO76 sensorless path

FO76 is different. The observer explicitly reconstructs applied alpha/beta voltage from PWM duty and Vbus:

```c
vbus_mv = (vbus_adc * vbus_mv_per_count_q16) >> 16;
valpha  = vbus_mv * PWM_vector_alpha;
vbeta   = vbus_mv * PWM_vector_beta;
```

The supplied `vbus_adc` is `pBusSensorM1->_Super.AvBusVoltage_d`, i.e. the same PA1-derived average.

The sensorless startup preload also calls `VescToSTM_get_bus_voltage()` and feeds that value into `g30_r3i_preload_calculate()`.

Therefore both:
1. FO76 applied-voltage reconstruction, and
2. sensorless startup/current-controller preload

inherit PA1 saturation.

At full 14S charge, 58.8 V:
- maximum represented PA1 voltage is about 47.223 V;
- missing voltage is about 11.58 V;
- observer voltage would be understated by about **19.7%**.

At 50.4 V:
- understatement is already about **6.3%**.

That error is too large to call the present sensorless path qualified for 14S.

## 6. BEMF channels cannot simply replace PA1

Historical G30/FO76 reference uses approximately:
- Vbus divider ratio 14,
- BEMF divider ratio 12.

A ratio-12 BEMF input has an even lower direct full-scale bus-equivalent voltage (about 39.6 V at 3.3 V). It cannot serve as a direct 58.8 V bus-voltage sensor.

## 7. SHUD(4) comparison

Known SHUD(4) changes include:
- battery current limit 39 A,
- phase current limit 55 A,
- DPC coefficient 110 and quadratic curve,
- current-raising coefficient 6500,
- braking and wheel-scaling changes,
- multiple additional NOP/jump patches whose exact effects are not all assigned.

The existing 46-span / 143-byte Stock-vs-SHUD patch list contains no **identified** PA1/Vbus gain patch. Because some patches remain semantically unresolved, this audit does not claim total Stock/SHUD voltage-path identity.

Historical high-voltage SHUD operation is nevertheless consistent with the Hall-inner-loop finding above. It does not prove FO76-style sensorless voltage reconstruction is correct at 14S.

## 8. What a software-only 14S solution must do

Changing `BATTERY_VOLTAGE_GAIN` alone cannot recover information after PA1 ADC saturation.

A valid software-only solution must provide an alternate high-voltage Vbus source for at least:
- FO76 observer voltage reconstruction,
- sensorless preload,
- 14S over-voltage protection / plausibility.

Candidate paths to investigate after the 27 V characterization:
1. model-based Vbus estimation using known PWM, phase currents, R/L/lambda and electrical speed, calibrated against PA1 below saturation;
2. an additional trusted external voltage source if one exists in the vehicle architecture.

The stock 10S BMS voltage cannot by itself be treated as total 14S Vbus because it does not measure the added 4S section.

## 9. VBUS_AUDIT_V1 hardware gate

The audit build is diagnostic-only and retains the existing hard power-stage lock:
- `R3_2_TurnOnLowSides` blocked,
- normal `R3_2_SwitchOnPWM` blocked,
- TIM1 MOE required to stay 0,
- no motor commands.

Test supply:
- EA PSU 27 V,
- stock battery disconnected,
- no 4S series pack,
- no 14S.

The hardware gate checks the real 27 V conversion, ADC alignment, headroom, threshold clipping, FO76-derived voltage scaling and hard power lock.

## 10. Release decision

**27 V VBUS audit: ready.**
**14S Hall road use: not released by this audit.**
**14S sensorless: explicitly not released until an alternate Vbus source/estimator is implemented and validated below saturation first.**
