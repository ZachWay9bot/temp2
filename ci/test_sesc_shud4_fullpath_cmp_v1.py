#!/usr/bin/env python3
from pathlib import Path
import hashlib

root=Path('SOURCE_KOXX3')
def txt(rel): return (root/rel).read_text()
def sha(rel): return hashlib.sha256((root/rel).read_bytes()).hexdigest()

# Proven fast motor path must remain byte-exact.
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
VH=txt('common_files/src/VescToSTM.h')
G=txt('common_files/src/g30_dash_link.c')
C=txt('common_files/src/conf_general.c')
L=txt('common_files/src/task_LED.c')
MC=txt('common_files/src/mc_tasks.c')

assert 'SESC-DRV126-P6500-H14-SHUD4PATH-CMP-V1' in D
assert '#define G30_SHUD4_FULLPATH_CMP_V1 1' in D
assert '#define G30_SHUD4_BMS_V1 1' in D
print('IDENTITY_BASELINE=PASS')

# Existing SHUD4 power/BMS values remain present.
for x in ['mcconf->l_current_max = 55.0f;','mcconf->l_current_min = -55.0f;','mcconf->l_in_current_max = 39.0f;']:
    assert x in C,x
for x in ['G30_BMS_PERIOD_MS 105u','reg=0x30u; ask=0x0Cu','HAL_UART_Transmit(&huart3']:
    assert x in L,x
assert '#define G30_DRV126_CURRENT_RAISING_COEFF_MA 6500' in MC
print('SHUD4_POWER_BMS_BASELINE=PASS')

# Direct current-reference handoff exists and is bounded for first bench test.
for x in [
    'G30_SHUD4_CMP_BENCH_MAX_MA 5000',
    'void VescToSTM_g30_shud4_cmp_hold_pwm(bool hold)',
    'void VescToSTM_g30_shud4_cmp_direct_ma(int32_t forward_ma)',
    'pwm_force=hold;',
    'VescToSTM_set_current(iq,0.0f);',
    '(void)MCI_StartMotor(pMCI[M1]);',
]:
    assert x in V,x
assert 'VescToSTM_g30_shud4_cmp_direct_ma' in VH
print('DIRECT_EXTERNAL_CURRENT_PATH=PASS')

# The comparison dashboard path must use SHUD DPC / request logic.
for x in [
    'G30_SHUD4_CMP_PHASE_LIMIT_MA 55000',
    'G30_SHUD4_CMP_OUTPUT_CAP_MA   5000',
    'G30_SHUD4_CMP_STEP_MS            5u',
    'G30_SHUD4_CMP_DRIVE_SLEW_MA   6500',
    'G30_SHUD4_CMP_RELEASE_FAST_MA  1500',
    'G30_SHUD4_CMP_RELEASE_LOW_MA    500',
    'G30_SHUD4_CMP_HOLD_RATE         500',
    'G30_SHUD4_CMP_LOW_RATE          400',
    '(int32_t)raw-55',
    '(110ll*110ll)',
]:
    assert x in G,x
print('SHUD_DPC_AND_STATE_CONSTANTS=PASS')

# No KERS: target/current path is never intentionally negative.
segment=G[G.index('#ifdef G30_SHUD4_FULLPATH_CMP_V1'):G.index('/* Called on legitimate IoT VESC')]
assert 'shud_target_ma=drive ?' in segment
assert 'shud_target_ma=-' not in segment
assert 'VescToSTM_set_brake' not in segment
assert 'VescToSTM_g30_pushstart_command' not in segment
print('NO_KERS_NO_SESC_COAST_CALLS=PASS')

# "No coast" comparison semantics: above rate 500, zero request keeps PWM forced.
service=G[G.index('static void g30_shud4_cmp_service'):G.index('#endif',G.index('static void g30_shud4_cmp_service'))]
assert 'if(rate>G30_SHUD4_CMP_HOLD_RATE)' in service
assert 'VescToSTM_g30_shud4_cmp_hold_pwm(true);' in service
assert 'VescToSTM_g30_shud4_cmp_direct_ma(d->shud_request_ma);' in service
# Hard off remains only for invalid/stale/fault/remote/low-speed safety.
assert 'g30_shud4_cmp_hard_off(d);' in service
print('ACTIVE_ZERO_CURRENT_HOLD_NOT_FREEWHEEL=PASS')

# The SESC speed-PI torque path must not be called by the SHUD comparison branch.
cmp_branch=G[G.index('#ifdef G30_SHUD4_FULLPATH_CMP_V1',G.index('g30_dash_r2_action action=')):
             G.index('#else',G.index('#ifdef G30_SHUD4_FULLPATH_CMP_V1',G.index('g30_dash_r2_action action=')))]
for forbidden in ['VescToSTM_set_current_rel_int','VescToSTM_update_torque','VescToSTM_set_torque']:
    assert forbidden not in cmp_branch,forbidden
print('SESC_SPEED_PI_BYPASSED_IN_DASH_PATH=PASS')

# Remote COM9 ownership remains available and forces a clean handoff.
claim=G[G.index('void g30_dash_link_vesc_claim'):G.index('bool g30_dash_link_brake_active')]
assert 'g30_shud4_cmp_hard_off(d);' in claim
print('COM9_REMOTE_HANDOFF_RETAINED=PASS')

# Sanity-check DPC math under the 5A bench cap.
def target(raw):
    n=max(0,min(120,raw-55))
    t=(55000*n*n)//12100
    return min(5000,t)
assert target(55)==0
assert 1700 < target(75) < 1900
assert target(100)==5000
assert target(175)==5000
print('DPC_MATH_SANITY=PASS',target(75),target(100),target(175))

# Release/request slews.
def slew(cur,tgt,step):
    d=tgt-cur
    if d>step:return cur+step
    if d<-step:return cur-step
    return tgt
assert slew(5000,0,1500)==3500
assert slew(3500,0,1500)==2000
assert slew(2000,0,1500)==500
assert slew(500,0,1500)==0
assert slew(5000,0,500)==4500
print('SHUD_RELEASE_SLEW_SANITY=PASS')

print('SHUD4_FULLPATH_CMP_V1_STATIC=PASS')
