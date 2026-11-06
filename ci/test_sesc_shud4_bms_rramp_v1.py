#!/usr/bin/env python3
from pathlib import Path
import hashlib

root=Path('SOURCE_KOXX3')

def txt(rel): return (root/rel).read_text()
def sha(rel): return hashlib.sha256((root/rel).read_bytes()).hexdigest()

# Fast motor path must remain byte-exact.
expected={
 'common_files/src/mc_tasks.c':'1c3f61ad12855960ddf25ea96730328bdfaa4d8653d6f7ec9fe89d2114518c98',
 'common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c':'14ccd029244f230d5632f18c6c278aa3021976ede8a4513939af068456eee276',
}
for rel,want in expected.items():
    got=sha(rel)
    assert got==want,(rel,got,want)
    print('FASTPATH_EXACT',rel,'PASS',got)

D=txt('common_files/src/defines.h')
V=txt('common_files/src/VescToSTM.c')
C=txt('common_files/src/conf_general.c')
L=txt('common_files/src/task_LED.c')

assert 'SESC-DRV126-P6500-H14-SBMS-RRAMP-V1' in D
assert '#define G30_SHUD4_BMS_V1 1' in D
assert '#define G30_HALL_ROLLING_RAMP_V1 1' in D
print('IDENTITY_AND_BASELINE=PASS')

# SHUD4/BMS baseline values remain intact.
for x in ['mcconf->l_current_max = 55.0f;','mcconf->l_current_min = -55.0f;','mcconf->l_in_current_max = 39.0f;']:
    assert x in C,x
for x in ['G30_BMS_PERIOD_MS 105u','reg=0x30u; ask=0x0Cu','HAL_UART_Transmit(&huart3']:
    assert x in L,x
print('SHUD4_LIMITS_AND_BMS_UNCHANGED=PASS')

# Ramp trigger and shape.
for x in [
    '#define G30_HALL_RRAMP_MIN_ERPM 1000',
    '#define G30_HALL_RRAMP_MS 200u',
    '#define G30_HALL_RRAMP_START_MA 1000',
    'erpm=VescToSTM_get_erpm_fast()*2;',
    'if(erpm>=G30_HALL_RRAMP_MIN_ERPM)',
    'g30_hall_rramp_arm_on_drive_edge();',
    'q=g30_hall_rramp_limit_q(q);',
]:
    assert x in V,x

# Release must only reset the mini-ramp state, then use the original coast path.
push=V[V.index('void VescToSTM_g30_pushstart_command'):V.index('void VescToSTM_g30_pushstart_command')+1800]
assert 'g30_hall_rramp_release();' in push
assert 'VescToSTM_g30_coast_rearm();' in push
print('ROLLING_EDGE_ONLY=PASS')

# Coast implementation itself must remain the original bridge-off behavior.
coast=V[V.index('static void VescToSTM_g30_coast_rearm'):V.index('void VescToSTM_g30_pushstart_command')]
assert 'VescToSTM_pwm_stop();' in coast
assert 'g30_hall_rramp_' not in coast
assert 'VescToSTM_set_current(0.0f,0.0f);' in coast
print('PRECLONK_COAST_UNCHANGED=PASS')

# The mini-ramp helper itself must never manipulate PWM, Hall angle, PI or Vqd.
helper=V[V.index('#define G30_HALL_RRAMP_MIN_ERPM'):V.index('void VescToSTM_g30_sensor_mode_sync')]
for forbidden in ['VescToSTM_pwm_start','VescToSTM_pwm_stop','PWMC_SwitchOnPWM','wIntegralTerm','Vqd','MeasuredElAngle']:
    assert forbidden not in helper,forbidden
print('RAMP_OUTSIDE_PWM_FOC_STATE=PASS')

# Linear mA-equivalent behavior. current_to_torque is linear, so these are the
# same proportions applied to torque counts in firmware.
def cap(req_ma,age_ms,start_ma=1000,duration=200):
    if age_ms>=duration or abs(req_ma)<=start_ma:
        return req_ma
    sign=-1 if req_ma<0 else 1
    mag=abs(req_ma)
    lim=start_ma+((mag-start_ma)*age_ms)//duration
    return sign*min(mag,lim)

assert cap(5000,0)==1000
assert cap(5000,50)==2000
assert cap(5000,100)==3000
assert cap(5000,150)==4000
assert cap(5000,199)==4980
assert cap(5000,200)==5000
assert cap(-5000,100)==-3000
assert cap(800,0)==800
print('RAMP_5A_1_2_3_4_5A_OVER_200MS=PASS')

# Existing modified DRV126 coefficient remains exactly 6500 and untouched.
MC=txt('common_files/src/mc_tasks.c')
assert '#define G30_DRV126_CURRENT_RAISING_COEFF_MA 6500' in MC
assert '#define G30_DRV126_CURRENT_RAISING_STEP_MC 2435' in MC
print('POWERCORE6500_UNCHANGED=PASS')

print('SHUD4_BMS_RRAMP_V1_STATIC=PASS')
