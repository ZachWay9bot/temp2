#!/usr/bin/env python3
"""V1.1 power-disabled diagnostic patch for exact LIVE_SHADOW_V1 source.
NO motor operation is intended or permitted in this build."""
from pathlib import Path
import re
root=Path("SOURCE_KOXX3")
def one(path, old, new):
    p=root/path
    src=p.read_text()
    assert src.count(old)==1,(str(p),src.count(old))
    p.write_text(src.replace(old,new,1))

one("common_files/src/defines.h",
    '#define HW_NAME "SESC-DRV126-POWERCORE6500-VBUS-FUSION-LIVE-SHADOW-V1"',
    '#define HW_NAME "SESC-DRV126-POWERCORE6500-SAFETY-DIAG-LOCKED-V11"\n#define G30_SAFETY_DIAG_POWER_LOCK 1')
p="common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c"
one(p,
    "#ifdef G30_BMS_BATTERY_SAFE_POWERLOCK\n  pHdl->PWM_off = true;",
    "#ifdef G30P\n  /* Verified G30P target macro: always lock MOE and low-side pins. */\n  pHdl->PWM_off = true;")
one(p,
"""#ifdef G30_BMS_BATTERY_SAFE_POWERLOCK
  if (LL_TIM_CC_IsEnabledChannel(TIMx,TIMxCCER_MASK_CH123) != 0u)
  {
    pHdl->PWM_off = true;
    pHandle->_Super.TurnOnLowSidesAction = false;
    LL_TIM_DisableAllOutputs(TIMx);
    if ((pHandle->pParams_str->LowSideOutputs) == ES_GPIO)
    {
      LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_u_port, pHandle->pParams_str->pwm_en_u_pin);
      LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_v_port, pHandle->pParams_str->pwm_en_v_pin);
      LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_w_port, pHandle->pParams_str->pwm_en_w_pin);
    }
    return;
  }
#endif""",
"""#ifdef G30P
  /* Unconditional hardware lock, even if CCER happens to be disabled. */
  pHdl->PWM_off = true;
  pHandle->_Super.TurnOnLowSidesAction = false;
  LL_TIM_DisableAllOutputs(TIMx);
  if ((pHandle->pParams_str->LowSideOutputs) == ES_GPIO)
  {
    LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_u_port, pHandle->pParams_str->pwm_en_u_pin);
    LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_v_port, pHandle->pParams_str->pwm_en_v_pin);
    LL_GPIO_ResetOutputPin(pHandle->pParams_str->pwm_en_w_port, pHandle->pParams_str->pwm_en_w_pin);
  }
  return;
#endif""")
p=root/"common_files/inc/product.h"
s=p.read_text()
s,n=re.subn(r"(?m)^#define AUTO_RESET_FAULT\s+1\s*$",
"""#ifdef G30P
#define AUTO_RESET_FAULT 0 /* fail-latched; no automatic restart */
#else
#define AUTO_RESET_FAULT 1
#endif""",s)
assert n==1,n
p.write_text(s)
one("common_files/src/conf_general.c",
"""	PWM_Handle_M1._Super.OverCurrent = (int16_t)oc_counts_f;

	if(mcconf->l_slow_abs_current){""",
"""#ifdef G30_SAFETY_DIAG_POWER_LOCK
    oc_counts_f = 8.0f * CURRENT_FACTOR_A;
#endif
	PWM_Handle_M1._Super.OverCurrent = (int16_t)oc_counts_f;

#ifdef G30_SAFETY_DIAG_POWER_LOCK
    PWM_Handle_M1._Super.OverCurrentCycles = 0;
#else
	if(mcconf->l_slow_abs_current){""")
one("common_files/src/conf_general.c",
"""		PWM_Handle_M1._Super.OverCurrentCycles = 0;  //instant trip
	}

	FOCVars[M1].max_i_batt""",
"""		PWM_Handle_M1._Super.OverCurrentCycles = 0;  //instant trip
	}
#endif

	FOCVars[M1].max_i_batt""")
print("SAFETY_DIAG_LOCKED_V11_APPLIED=PASS")
