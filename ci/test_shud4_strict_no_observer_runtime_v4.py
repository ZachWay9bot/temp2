#!/usr/bin/env python3
from pathlib import Path
import sys,re
R=Path('SOURCE_KOXX3')
d=(R/'common_files/src/defines.h').read_text()
v=(R/'common_files/src/VescToSTM.c').read_text()
m=(R/'common_files/src/mc_tasks.c').read_text()
i=(R/'common_files/src/stm32f10x_mc_it.c').read_text()
checks=[]
def ck(n,x):
    checks.append((n,bool(x)))
    print(f'{n}={"PASS" if x else "FAIL"}')
ck('BUILD_ID_V4','SHUD4-STRICT-DRIVE-V4' in d)
ck('STRICT_SENSORLESS_FALSE',re.search(r'G30_SHUD4_STRICT_DRIVETRAIN_V1\)\s*\n\s*return false;',v) is not None)
ck('STRICT_HALL_TRUE',re.search(r'bool VescToSTM_g30_hall_selected\(void\).*?G30_SHUD4_STRICT_DRIVETRAIN_V1\)\s*\n\s*return true;',v,re.S) is not None)
ck('STRICT_DIRECT_HALL_SPEED','STRICT SHUD4: Hall is the sole electrical position/speed source' in m)
ck('CONTROL_ANGLE_COMPILE_GUARDED','#ifndef G30_SHUD4_STRICT_DRIVETRAIN_V1\n  /* R3G: Hall is still the default.' in m)
ck('DRV_OBSERVER_COMPILE_GUARDED','#ifndef G30_SHUD4_STRICT_DRIVETRAIN_V1\n    if(VescToSTM_g30_sensorless_selected())' in m)
ck('GENERIC_OBSERVER_COMPILE_GUARDED',m.count('#ifndef G30_SHUD4_STRICT_DRIVETRAIN_V1')>=5)
ck('OBSERVER_COAST_EXCLUDED','R3H observer-only exit is not part of STRICT SHUD4' in m)
ck('HALL_TRACE_NO_OBSERVER_CALL','probe.control=(uint16_t)HALL_M1._Super.hElAngle;' in i)
ck('NATIVE_TIMING_RETAINED','#define PWM_FREQUENCY   8000' in (R/'common_files/inc/drive_parameters.h').read_text())
ck('NATIVE_GATE_RETAINED','TIM1->CCER=0x1000u;' in m and 'TIM1->CCER=0x1555u;' in m)
if not all(v for _,v in checks): sys.exit(2)
print('SHUD4_STRICT_NO_OBSERVER_RUNTIME_V4_STATIC=PASS')
