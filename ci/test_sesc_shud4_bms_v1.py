#!/usr/bin/env python3
from pathlib import Path
import hashlib,re
root=Path('SOURCE_KOXX3')

def txt(rel): return (root/rel).read_text()
def sha(rel): return hashlib.sha256((root/rel).read_bytes()).hexdigest()

# Frozen Hall fast motor path must remain byte-exact.
expected={
 'common_files/src/mc_tasks.c':'1c3f61ad12855960ddf25ea96730328bdfaa4d8653d6f7ec9fe89d2114518c98',
 'common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c':'14ccd029244f230d5632f18c6c278aa3021976ede8a4513939af068456eee276',
}
for rel,want in expected.items():
    got=sha(rel); assert got==want,(rel,got,want)
    print('FASTPATH_EXACT',rel,'PASS',got)

D=txt('common_files/src/defines.h')
C=txt('common_files/src/conf_general.c')
M=txt('common_files/inc/mcconf_default.h')
G=txt('common_files/src/g30_dash_drive_logic.h')
L=txt('common_files/src/task_LED.c')
T=txt('common_files/src/terminal.c')
P=txt('common_files/inc/product.h')
MC=txt('common_files/src/mc_tasks.c')
R3=txt('common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c')
V=txt('common_files/src/VescToSTM.c')

assert 'SESC-DRV126-P6500-HALL14S-SHUD4BMS-V1' in D
assert '#define G30_SHUD4_BMS_V1 1' in D
for x in ['mcconf->l_current_max = 55.0f;','mcconf->l_current_min = -55.0f;','mcconf->l_in_current_max = 39.0f;']:
    assert x in C,x
assert 'MCCONF_L_CURRENT_MAX\t\t\t55.0' in M
assert 'MCCONF_L_CURRENT_MIN\t\t\t-55.0' in M
assert 'MCCONF_L_IN_CURRENT_MAX\t\t\t39.0' in M
print('SHUD_LIMITS_55A_PHASE_39A_BATT=PASS')

assert '#define G30_DRV126_CURRENT_RAISING_COEFF_MA 6500' in MC
assert '#define G30_DRV126_CURRENT_RAISING_STEP_MC 2435' in MC
print('SHUD_CURRENT_RAISING_COEFF_6500_IN_FROZEN_PATH=PASS')

assert '(int32_t)gas-55' in G and 'if(n>120) n=120;' in G
assert '(110u*110u)' in G and 'if(q15>32768u) q15=32768u;' in G
def scale(gas):
    n=max(0,min(120,gas-55)); return min(32768,(n*n*32768)//12100)
assert scale(55)==0 and scale(165)==32768 and scale(175)==32768
assert 11000 < scale(121) < 12500
print('SHUD_DPC_QUADRATIC_COEFF_110=PASS')

assert 'true coast' in V and 'VescToSTM_set_brake(0);' in V
print('NO_KERS_COAST_POLICY=PASS')

assert '#define VESC_USART' in P and 'USART1' in P.split('#ifdef G30P',1)[1].split('#endif',1)[0]
assert '#define APP2_USART_DMA' in P and 'huart3' in P.split('#ifdef G30P',1)[1].split('#endif',1)[0]
print('BMS_USART3_SEPARATE_FROM_VESC_USART1=PASS')

for x in ['out[0]=0x5Au','out[1]=0xA5u','out[3]=0x20u','out[4]=0x22u','out[5]=0x01u',
          'reg=0x10u; ask=0x10u','reg=0x30u; ask=0x0Cu','G30_BMS_PERIOD_MS 105u']:
    assert x in L,x
assert 'g30_bms->cmd!=0x04u' in L
assert 'HAL_UART_Receive_DMA(&huart3' in L
assert 'HAL_UART_Transmit(&huart3' in L
assert '% G30_BMS_RX_N' in L
segment=L[L.index('#ifdef G30_SHUD4_BMS_V1'):L.index('#endif',L.index('int16_t g30_bms_stock_current'))+6]
assert 'out[5]=0x03u' not in segment
assert 'g30_bms_service_10ms();' in L
assert 'g30_bms' not in MC.lower()
assert 'g30_bms' not in R3.lower()
print('BMS_STOCK_READ_HEARTBEAT_10_30_105MS=PASS')
print('BMS_NO_WRITES_NO_FOC_NO_PWM_HOOK=PASS')

assert 'static g30_bms_stock_state_t *g30_bms;' in L
assert 'pvPortMalloc(sizeof(*g30_bms))' in L
print('BMS_HEAP_BACKED_FOR_TIGHT_SRAM=PASS')

assert 'strcmp(argv[0], "g30_bms")' in T and 'BMS stockhb present=' in T
print('BMS_TERMINAL_DIAGNOSTIC=PASS')
print('SHUD4_BMS_V1_STATIC=PASS')
