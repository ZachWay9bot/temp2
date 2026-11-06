#!/usr/bin/env python3
from pathlib import Path
import hashlib,re

root=Path('SOURCE_KOXX3')
def txt(rel): return (root/rel).read_text()
def sha(rel): return hashlib.sha256((root/rel).read_bytes()).hexdigest()

# Keep proven Hall fast FOC/PWM path exact.
expected={
 'common_files/src/mc_tasks.c':'1c3f61ad12855960ddf25ea96730328bdfaa4d8653d6f7ec9fe89d2114518c98',
 'common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c':'14ccd029244f230d5632f18c6c278aa3021976ede8a4513939af068456eee276',
}
for rel,want in expected.items():
    got=sha(rel); assert got==want,(rel,got,want)
    print('FASTPATH_EXACT',rel,'PASS',got)

D=txt('common_files/src/defines.h')
V=txt('common_files/src/VescToSTM.c')
C=txt('common_files/src/conf_general.c')
L=txt('common_files/src/task_LED.c')

assert 'SESC-DRV126-P6500-H14-SHUD4BMS-CLONKFREE-V1' in D
assert '#define G30_SHUD4_CLONKFREE_V1 1' in D
assert '#define G30_SHUD4_COAST_HOLD_ERPM 500' in V
print('IDENTITY_AND_SHUD_THRESHOLD=PASS')

# Coast hold must only preserve an already-running Hall bridge.
fn=V[V.index('static bool g30_shud4_coast_hold_allowed(void){'):V.index('bool VescToSTM_g30_hall_direction_allowed')]
for x in [
    'VescToSTM_g30_hall_selected()',
    'PWM_Handle_M1._Super.PWM_off',
    'VescToSTM_g30_hall_feedback_valid()',
    'return erpm>G30_SHUD4_COAST_HOLD_ERPM;'
]: assert x in fn,x
assert 'VescToSTM_pwm_start' not in fn
print('COAST_HOLD_NEVER_ENERGIZES_FROM_ZERO=PASS')

coast=V[V.index('static void VescToSTM_g30_coast_rearm'):V.index('void VescToSTM_g30_pushstart_command')]
assert 'if(g30_shud4_coast_hold_allowed())' in coast
assert 'VescToSTM_set_current(0.0f,0.0f);' in coast
hold=coast[coast.index('if(g30_shud4_coast_hold_allowed())'):coast.index('/* True bridge-off coast')]
assert 'VescToSTM_pwm_stop' not in hold
assert 'VescToSTM_pwm_start' not in hold
assert 'VescToSTM_pwm_stop();' in coast[coast.index('/* True bridge-off coast'):]
print('ROLLING_ZERO_CURRENT_KEEPS_PWM_LOW_SPEED_STOPS=PASS')

# Auto PWM-off hook must not kill the held rolling state.
hook=V[V.index('int16_t VescToSTM_Iq_lim_hook'):V.index('int32_t VescToSTM_rpm_to_speed')]
assert 'shud_coast_hold' in hook
assert 'g30_shud4_coast_hold_allowed()' in hook
print('PWM_OFF_HOOK_RESPECTS_SHUD_COAST_HOLD=PASS')

# No KERS / no active braking policy remains.
brake=V[V.index('void VescToSTM_set_brake(int32_t current)'):V.index('void VescToSTM_set_speed')]
assert 'VescToSTM_g30_coast_rearm();' in brake
assert 'MCI_ExecSpeedRamp' not in brake.split('#endif',1)[0]
print('NO_KERS_COAST_ONLY=PASS')

# SHUD4 performance and BMS layer unchanged.
for x in ['mcconf->l_current_max = 55.0f;','mcconf->l_current_min = -55.0f;','mcconf->l_in_current_max = 39.0f;']:
    assert x in C,x
assert 'G30_BMS_PERIOD_MS 105u' in L
assert 'HAL_UART_Receive_DMA(&huart3' in L and 'HAL_UART_Transmit(&huart3' in L
print('SHUD4_LIMITS_AND_BMS_UNCHANGED=PASS')

# Explicitly preserve HALL14S zero-preload only for a true PWM start. Rolling
# restart should bypass this because PWM stays on.
assert 'if(PWM_Handle_M1._Super.PWM_off)' in V
assert 'PIDIqHandle_M1.wIntegralTerm = 0;' in V
assert 'motor_voltage = 0.0f;' in V
print('TRUE_START_ZERO_PRELOAD_UNCHANGED=PASS')

print('SHUD4_CLONKFREE_V1_STATIC=PASS')
