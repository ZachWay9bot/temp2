#!/usr/bin/env python3
from pathlib import Path
import hashlib
root=Path('SOURCE_KOXX3')

def txt(rel): return (root/rel).read_text()
def sha(rel): return hashlib.sha256((root/rel).read_bytes()).hexdigest()

D=txt('common_files/src/defines.h')
C=txt('common_files/src/conf_general.c')
V=txt('common_files/src/VescToSTM.c')
MC=txt('common_files/src/mc_tasks.c')
G=txt('common_files/src/g30_dash_drive_logic.h')
L=txt('common_files/src/g30_dash_link.c')
VC=txt('common_files/src/VescCommand.c')
B=txt('common_files/src/task_LED.c')

assert 'SESC-DRV126-P6500-H14-SBMS-SHUD4DRIVE-V1' in D
assert '#define G30_SHUD4_FULL_DRIVETRAIN_V1 1' in D
print('IDENTITY=PASS')

for x in ['mcconf->l_current_max = 55.0f;','mcconf->l_current_min = -55.0f;','mcconf->l_in_current_max = 39.0f;']:
    assert x in C,x
assert '(int32_t)gas-55' in G and '(110u*110u)' in G
assert '#define G30_DRV126_CURRENT_RAISING_COEFF_MA 6500' in MC
assert '#define G30_DRV126_CURRENT_RAISING_STEP_MC 2435' in MC
print('SHUD_DRIVE_55A_39A_DPC110_RAISE6500=PASS')

for x in ['void VescToSTM_g30_shud4_idle(void)',
          'MCI_SetCurrentReferences(pMCI[M1],zero);',
          'void VescToSTM_g30_safe_coast(void)',
          'VescToSTM_g30_coast_rearm();']:
    assert x in V,x
assert '#ifdef G30_SHUD4_FULL_DRIVETRAIN_V1' in C and 'VescToSTM_set_minimum_current(0);' in C
assert 'G30_DASH_R2_IDLE' in G and 'G30_DASH_R2_SAFE_COAST' in G
assert 'G30_DASH_R2_COAST' not in G
assert 'VescToSTM_g30_shud4_idle();' in L
assert 'VescToSTM_g30_safe_coast();' in L
print('NO_KERS_ZERO_IQ_AND_FAILSAFE_COAST=PASS')

for x in ['G30_SHUD4_BRAKE_VIRTUAL_LIMIT 130u',
          'G30_SHUD4_BRAKE_MIN_MA       5000u',
          'G30_SHUD4_BRAKE_MAX_MA      30000u']:
    assert x in G,x
for x in ['if(current<5000) current=5000;','if(current>30000) current=30000;',
          'VescToSTM_mode = STM_STATE_BRAKE;','const bool allow_braking = false;']:
    assert x in V,x
assert '#define G30_DRV126_BRAKE_RAISING_COEFF_MA 500' in MC
assert '#define G30_DRV126_BRAKE_RAISING_STEP_MC 187' in MC
assert 'if(VescToSTM_mode==STM_STATE_BRAKE) qstep=G30_DRV126_BRAKE_RAISING_STEP_MC;' in MC
assert 'VescToSTM_set_brake((int32_t)brake_ma);' in L
assert 'VescToSTM_set_brake((int32_t)g30_dash_link_brake_current_ma());' in VC
print('SHUD_BRAKE_130_5A_30A_RAISE500=PASS')

def dpc(gas):
    n=max(0,min(120,gas-55))
    return min(32768,(n*n*32768)//12100)

def brake_ma(brake):
    if brake<45: return 0
    brake=min(210,brake)
    virt=((brake-45)*130)//(210-45)
    return min(30000,5000+(virt*25000)//130)

assert dpc(55)==0 and dpc(165)==32768 and 11000<dpc(121)<12500
assert brake_ma(44)==0 and brake_ma(45)==5000 and brake_ma(210)==30000
assert 16000<brake_ma(121)<18000
print('CURVE_NUMERIC_SANITY=PASS')

for x in ['G30_BMS_PERIOD_MS 105u','reg=0x30u; ask=0x0Cu','HAL_UART_Transmit(&huart3']:
    assert x in B,x
print('BMS_BASELINE_RETAINED=PASS')

assert sha('common_files/src/mc_tasks.c')=='627e4b507d2b4634a228a1353f1f5f99dceb03fd4b7f85b067cb09f8ad08d139'
assert sha('common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c')=='14ccd029244f230d5632f18c6c278aa3021976ede8a4513939af068456eee276'
print('CURRENT_CORE_EXPECTED_DELTA_PWM_BACKEND_EXACT=PASS')

timeout=V[V.index('void VescToSTM_handle_timeout'):V.index('void VescToSTM_enable_timeout')]
assert 'VescToSTM_g30_safe_coast();' in timeout
print('PROTECTION_BYPASS_NOT_PORTED_TIMEOUT_FAILSAFE=PASS')
print('SHUD4_FULL_DRIVETRAIN_V1_STATIC=PASS')
