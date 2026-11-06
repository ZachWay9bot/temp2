#!/usr/bin/env python3
"""Static locked-V11 contract. Must be combined with post-link assembly checks."""
from pathlib import Path
root=Path("SOURCE_KOXX3")
defs=(root/"common_files/src/defines.h").read_text()
pwm=(root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c").read_text()
product=(root/"common_files/inc/product.h").read_text()
conf=(root/"common_files/src/conf_general.c").read_text()
assert 'HW_NAME "SESC-DRV126-POWERCORE6500-SAFETY-DIAG-LOCKED-V11"' in defs
assert '#define G30_SAFETY_DIAG_POWER_LOCK 1' in defs
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' not in pwm
low=pwm[pwm.index("void R3_2_TurnOnLowSides("):pwm.index("void R3_2_SwitchOnPWM(")]
on=pwm[pwm.index("void R3_2_SwitchOnPWM("):pwm.index("void R3_2_SwitchOffPWM(")]
for name,s in [("low",low),("on",on)]:
    assert "#ifdef G30P" in s
    guard=s[s.index("#ifdef G30P"):s.index("#endif",s.index("#ifdef G30P"))]
    assert "LL_TIM_DisableAllOutputs(TIMx);" in guard
    assert "pHdl->PWM_off = true;" in guard
    assert "return;" in guard
    assert "LL_GPIO_ResetOutputPin" in guard
assert "LL_TIM_CC_IsEnabledChannel(TIMx,TIMxCCER_MASK_CH123) != 0u" not in on[:on.index("#endif",on.index("#ifdef G30P"))]
assert "#define AUTO_RESET_FAULT 0" in product
assert "#ifdef G30_SAFETY_DIAG_POWER_LOCK" in conf
assert "OverCurrentCycles = 0;" in conf
print("SOURCE_GUARD=PASS")
print("AUTORESTART_DISABLED=PASS")
print("OCP_DIAGNOSTIC_CONFIG=PASS")
