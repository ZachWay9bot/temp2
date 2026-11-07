#!/usr/bin/env python3
from pathlib import Path
import sys,re
R=Path('SOURCE_KOXX3')
d=(R/'common_files/src/defines.h').read_text()
p=(R/'common_files/inc/drive_parameters.h').read_text()
v=(R/'common_files/src/VescToSTM.c').read_text()
m=(R/'common_files/src/mc_tasks.c').read_text()
checks=[]
def ck(n,x): checks.append((n,bool(x))); print(f'{n}={"PASS" if x else "FAIL"}')
ck('BUILD_ID_V3','SHUD4-STRICT-DRIVE-V3' in d)
ck('NATIVE_PWM_8KHZ','#define PWM_FREQUENCY   8000' in p)
ck('NATIVE_OFF_CCR4_3800','TIM1->CCR4=3800u;' in v and 'TIM1->CCR4=3800u;' in m)
start=m.index('/* STRICT SHUD4 native timing:')
end=m.index('#else',start)
strict_timing=m[start:end]
ck('NATIVE_CONTROL_DIV2','g30_drv126_final_div=0u;' in strict_timing and 'g30_drv126_final_div=1u;' in strict_timing and '&3u' not in strict_timing)
sv=m[m.index('/* STRICT SHUD4: native DRV126 SVPWM'):m.index('#else',m.index('/* STRICT SHUD4: native DRV126 SVPWM'))]
ck('NATIVE_SVPWM_0_4000',all(x in sv for x in ['uint16_t c1=r1;','uint16_t c2=r2;','uint16_t c3=r3;']) and '>>1' not in sv)
ck('NATIVE_CCER_OFF_ON','TIM1->CCER=0x1000u;' in m and 'TIM1->CCER=0x1555u;' in m)
ck('NO_HSYNC_MACRO','#define G30_HALL_ROLLING_SYNC_V1 1' not in d)
if not all(v for _,v in checks): sys.exit(2)
print('SHUD4_STRICT_NATIVE_TIMING_V3_STATIC=PASS')
