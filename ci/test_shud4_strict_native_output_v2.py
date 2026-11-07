#!/usr/bin/env python3
from pathlib import Path
import sys
R=Path('SOURCE_KOXX3/common_files/src')
v=(R/'VescToSTM.c').read_text()
m=(R/'mc_tasks.c').read_text()
d=(R/'defines.h').read_text()
checks=[]
def ck(n,x):
    checks.append((n,bool(x))); print(f'{n}={"PASS" if x else "FAIL"}')
ck('BUILD_ID_V2','SHUD4-STRICT-DRIVE-V2' in d)
start=v.index('void VescToSTM_g30_shud4_apply_request')
end=v.index('#endif',start)
strict=v[start:end]
ck('NORMAL_OFF_NO_MCSDK_MOE_KILL','PWMC_SwitchOffPWM' not in strict)
ck('NATIVE_OFF_CCER1000','TIM1->CCER=0x1000u;' in strict)
ck('NATIVE_OFF_CCR4_SCALE','TIM1->CCR4=1900u;' in strict)
ck('NATIVE_OFF_FLAG','PWM_Handle_M1._Super.PWM_off=true;' in strict)
ck('REENGAGE_NO_SESC_PWM_START','VescToSTM_pwm_start();' not in strict)
ck('REENGAGE_ARM_ONLY','PWM_Handle_M1._Super.PWM_off=false;' in strict)
ck('FAST_OFF_NATIVE_GATE',all(x in m for x in ['if(pHdl->PWM_off){','TIM1->CCER=0x1000u;','TIM1->CCR4=1900u;']))
ck('SVPWM_RECONNECT_1555','TIM1->CCER=0x1555u;' in m)
ck('INVALID_HALL_FULL_KILL','PWMC_SwitchOffPWM(pHdl);' in m)
ck('MOE_NOT_CLEARED_IN_NORMAL_OFF','LL_TIM_DisableAllOutputs' not in strict)
if not all(v for _,v in checks): sys.exit(2)
print('SHUD4_STRICT_NATIVE_OUTPUT_V2_STATIC=PASS')
