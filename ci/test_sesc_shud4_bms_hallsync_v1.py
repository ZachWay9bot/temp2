#!/usr/bin/env python3
from pathlib import Path
import hashlib

root=Path('SOURCE_KOXX3')
def txt(rel): return (root/rel).read_text()
def sha(rel): return hashlib.sha256((root/rel).read_bytes()).hexdigest()

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
H=txt('common_files/MotorControl/MCSDK/MCLib/Any/Src/hall_speed_pos_fdbk.c')
C=txt('common_files/src/conf_general.c')
L=txt('common_files/src/task_LED.c')

assert 'SESC-DRV126-P6500-H14-SBMS-HSYNC-V1' in D
assert '#define G30_HALL_ROLLING_SYNC_V1 1' in D
assert '#define G30_SHUD4_BMS_V1 1' in D
print('IDENTITY_BASELINE=PASS')

for x in ['mcconf->l_current_max = 55.0f;','mcconf->l_current_min = -55.0f;','mcconf->l_in_current_max = 39.0f;']:
    assert x in C,x
for x in ['G30_BMS_PERIOD_MS 105u','reg=0x30u; ask=0x0Cu','HAL_UART_Transmit(&huart3']:
    assert x in L,x
print('SHUD4_BMS_BASELINE_UNCHANGED=PASS')

# Original pre-clonk coast stays bridge-off.
coast=V[V.index('static void VescToSTM_g30_coast_rearm'):V.index('void VescToSTM_g30_pushstart_command')]
assert 'VescToSTM_pwm_stop();' in coast
assert 'VescToSTM_set_current(0.0f,0.0f);' in coast
assert 'ROLLING_SYNC' not in coast
assert 'g30_hall_prepare_pwm_reentry_angle' not in coast
print('PRECLONK_COAST_UNCHANGED=PASS')

# Hall driver confirms timer reset on each Hall edge and continuous angle mode.
MAIN=txt('g30p/Src/main.c')
HAL=txt('g30p/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_tim_ex.c')
assert 'HAL_TIMEx_HallSensor_Init(&htim3' in MAIN
assert 'TIM_SLAVEMODE_RESET' in HAL and 'TIM_TS_TI1F_ED' in HAL
assert 'pHandle->_Super.hElAngle += pHandle->_Super.hElSpeedDpp + pHandle->CompSpeed;' in H
assert 'if(abs(pHandle->_Super.hAvrMecSpeedUnit) > pHandle->SwitchSpeed)' in H
print('HALL_TIMER_EDGE_RESET_AND_INTERPOLATION=PASS')

# New helper must use elapsed Hall timer + signed dpp and preserve rolling speed state.
helper=V[V.index('#define G30_HALL_ROLLING_SYNC_MIN_ERPM'):V.index('void VescToSTM_pwm_start')]
for x in [
 '#define G30_HALL_ROLLING_SYNC_MIN_ERPM 1000',
 'HALL_M1.TIMx->CNT',
 'HALL_M1.TIMx->PSC+1u',
 'HALL_M1._Super.hMeasurementFrequency',
 'HALL_M1.TIMClockFreq',
 'HALL_M1._Super.hElSpeedDpp',
 'HALL_M1._Super.hElAngle=seed;',
 'HALL_M1.CompAngle=seed;',
 'HALL_M1.CompSpeed=0;',
]:
    assert x in helper,x
rolling=helper[helper.index('if(VescToSTM_g30_hall_selected()'):helper.index('/* Original HALL14S standstill')]
assert 'hAvrMecSpeedUnit=0' not in rolling
assert 'hElSpeedDpp=0' not in rolling
assert 'AvrElSpeedDpp=0' not in rolling
print('ROLLING_SPEED_STATE_PRESERVED=PASS')

# Standstill fallback must exactly reset speed as before.
fallback=helper[helper.index('/* Original HALL14S standstill'): ]
assert 'HALL_M1._Super.hElAngle=HALL_M1.MeasuredElAngle;' in fallback
assert 'HALL_M1.CompSpeed=0;' in fallback
assert 'HALL_M1._Super.hAvrMecSpeedUnit=0;' in fallback
print('STANDSTILL_START_BEHAVIOR_RETAINED=PASS')

# pwm_start still zero-preloads PI/Vqd, only angle/speed seed changes.
pwm=V[V.index('void VescToSTM_pwm_start'):V.index('void VescToSTM_update_torque')]
for x in [
 'PIDIqHandle_M1.wIntegralTerm = 0;',
 'PIDIdHandle_M1.wIntegralTerm = 0;',
 'FOCVars[M1].Vqd.q = 0;',
 'FOCVars[M1].Vqd.d = 0;',
 'motor_voltage = 0.0f;',
 'g30_hall_prepare_pwm_reentry_angle();',
 'PWMC_SwitchOnPWM(&PWM_Handle_M1._Super);'
]:
    assert x in pwm,x
print('ONLY_PWM_REENTRY_ANGLE_STATE_CHANGED=PASS')

# Formula sanity: 90 electrical Hz, 16 kHz FOC => ~369 dpp.
# 0.9 ms since edge should extrapolate roughly 29 degrees, under one sector.
def seed_delta(cnt,psc,timclk,meas_hz,dpp):
    cycles=(cnt*psc*meas_hz + timclk//2)//timclk
    adpp=abs(dpp)
    sector=65536//6
    max_cycles=(sector+adpp-1)//adpp
    cycles=min(cycles,max_cycles)
    delta=cycles*dpp
    return max(-sector,min(sector,delta))
dpp=round(65536*90/16000)
delta=seed_delta(int(64_000_000*0.0009),1,64_000_000,16000,-dpp)
assert -7000 < delta < -4000,(dpp,delta)
assert abs(seed_delta(65535,16,64_000_000,16000,-dpp)) <= 65536//6
print('ANGLE_EXTRAPOLATION_SANITY=PASS',dpp,delta)

print('SHUD4_BMS_HSYNC_V1_STATIC=PASS')
