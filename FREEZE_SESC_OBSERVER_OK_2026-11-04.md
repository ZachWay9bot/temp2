# FREEZE — SESC Observer OK — 2026-11-04

Freeze name: **SESC Observer OK**

## Frozen firmware
- Repository: `ZachWay9bot/temp2`
- Freeze branch: `freeze-sesc-observer-ok-20261104`
- Frozen source commit: `af46161167b9db28103abeb82fc7cfca6a6456d4`
- Build ID: `SESC-HYBRID-DEVV0.2`
- CI run: `41851592442` — SUCCESS
- Artifact: `G30D_SESC_HYBRID_DEVV02_COMPILED`
- Artifact ID: `13336545978`
- BIN SHA256: `adec609f98f084417243564cd1c7be199434e43503d7be3ae053a80e8eaeb618`
- Flash: 92432 / 118784 bytes
- Static RAM: 20388 / 20480 bytes
- Static RAM reserve: 92 bytes

## Scope of this freeze
This freeze marks the forward sensorless observer path as the validated baseline.

Required behavior:
- Hall mode: FWD + REV
- Sensorless mode: FWD only
- Sensorless pushstart from rolling wheel, approx. >= 3 km/h
- Brake policy: Coast, no regen
- Hall and sensorless remain separate selectable modes

## Hardware evidence inherited from DevV0.1
DevV0.1 completed:
- first guided test: 3/3 successful sensorless cycles
- second guided test: 5/5 successful sensorless cycles
- cumulative: 8/8 successful cycles
- 0 observer fallbacks
- 0 clamps
- 0 motor faults
- repeated Coast -> Rearm -> Restart successful
- stable observer operation observed down to 18.904 V Vbus

## DevV0.2 delta
DevV0.2 intentionally leaves the observer and pushstart core unchanged relative to DevV0.1.

Only these functional startup guards were added around the validated observer path:
1. In G30 sensorless mode, MCSDK CLEAR must not directly enable PWM.
2. Immediately before the first real sensorless PWM enable, existing Iq reference is capped to +/-1 A.
3. The proven 800 ms 1 A hold and following 1000 ms current ramp remain unchanged.

Observer constants remain unchanged:
- R_eff = 583 mOhm
- L_eff = 640 uH
- lambda_eff = 24200 uWb
- foc_hz = 16000
- pushstart minimum = 64 dpp

## Do not change inside this freeze
- FO76 observer model / estimator logic
- R/L/lambda values
- 64 dpp pushstart threshold
- 800 ms 1 A catch hold
- 1000 ms current ramp
- Hall LUT / Hall FOC path
- HS3 dashboard Vbus gate fix
- coast-only brake policy
- IoT/VESC UART
- bootloader / flash origin / option bytes / RDP

## Known non-blocking items outside observer acceptance
- DevV0.2 start guards are CI/source validated but not yet separately hardware-tested.
- True observer-fallback latch/recovery has not been deliberately forced on hardware after DevV0.1 became stable.
- Static RAM reserve is only 92 bytes; avoid adding global/static allocations.
- No independent IWDG is enabled.
- Existing dormant temperature-derating mapping typo should be fixed only when real temperature sensing is enabled.
- Sensorless reverse is intentionally out of scope and not required.

## Release rule
Any future observer, pushstart, R/L/lambda, 64-dpp threshold, catch-hold, or current-ramp experiment must branch from this freeze and must not overwrite it.

This freeze is the return point for the validated forward sensorless observer path.
