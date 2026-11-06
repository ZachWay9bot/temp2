# FREEZE – SESC POWERCORE6500 POWERPATH RESTORE V1 – HARDWARE OK – 2026-11-06

Hardware proof run: 20261106_191045

Build:
SESC-DRV126-POWERCORE6500-POWERPATH-RESTORE-V1

Parent hardware-confirmed source:
- POWERCORE6500 FINAL V1
- source commit bb76be300f082f0ffded43d76a318db3aa2d669c
- CI run 42040326759
- artifact 13421975037

Restore build:
- branch powerpath-restore-v1-20261106
- CI run 42267144640
- artifact 13528555020
- BIN SHA256 d0bbc8f5144dfa8771fd14f91db3b7e3eecde0add6634a26f70ed57afc6762b6

Hardware proof at 27 V with series halogen limiter:
- PREFLIGHT PASS
- Hall torque +1500 mA PASS
- Hall torque +3000 mA PASS
- Hall speed +1200 ERPM command PASS (no fault)
- final fault_now=0x0000
- final fault_occurred=0x0000
- state RUN=6
- coast PWM_off=1, MOE=0
- current offsets stayed exactly 32697 / 32896 / 32953
- FOC max 2052 / 4000 = 51 %
- COM9 valid packets 101
- COM9 CRC bad 0

Conclusion:
Restoring the exact POWERCORE6500 FINAL V1 motor/PWM/ADC/FO76 path removes the MC_FOC_DURATION failures seen in the later BMS/VBUS/FAULTGUARD-derived builds. This proves that one or more changes introduced after FINAL V1 were responsible for the regression. It does not by itself identify a single unique offending change because multiple later motor-path changes were removed together.

Removed from the restore motor path:
- BMS battery-safe powerlock
- BMS PHY sampling from the high-frequency motor path
- VBUS fusion calls from the high-frequency motor path
- LIVE_SHADOW_GATE clamps/takeover suppression
- BMS 10 ms LED-task service
- later UART3/BMS motor-test changes

Policy:
- Use this build as the new motor-path regression baseline.
- Do not add BMS work inside the 16 kHz FOC path.
- BMS/VBUS code may observe and request coast/fault, but must not own PWM start or alter ADC/TIM1 sequencing.
- Reintroduce later features one isolated change at a time with this hardware proof as regression gate.
