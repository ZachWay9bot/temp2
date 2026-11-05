#!/usr/bin/env python3
from pathlib import Path

root=Path("SOURCE_KOXX3")
de=(root/"common_files/src/defines.h").read_text()
led=(root/"common_files/src/task_LED.c").read_text()
te=(root/"common_files/src/terminal.c").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
mc=(root/"common_files/src/mc_tasks.c").read_text()
r3=(root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c").read_text()

assert 'SESC-DRV126-POWERCORE6500-BMS-FINALREAD-V1' in de
assert '#define G30_BMS_BATTERY_SAFE_POWERLOCK 1' in de
assert 'G30 BMS FINALREAD V1' in led
assert 'G30_BMS_STATUS_PERIOD_MS 110u' in led
assert 'g30_bms_final_send(0x30u,12u)' in led
assert 'g30_bms_final_send(0x40u,20u)' in led
assert 'huart3.Init.BaudRate=115200u' in led
assert '76800' not in led[led.index('G30 BMS FINALREAD V1'):led.index('void prv_LED_blink')]
assert 'out[5]=0x01u' in led
assert 'out[3]=0x20u;out[4]=0x22u' in led
assert 'out[5]=0x02u' not in led
assert 'CMD_WRITE' not in led
assert 'g30_bms_final_decode' in led
assert 'BF(current_raw)=(int16_t)g30_bms_u16(p+6)' in led
assert 'BF(pack_raw)=g30_bms_u16(p+8)' in led
assert 'BF(temp_raw)=g30_bms_u16(p+10)' in led
assert 'BF(cell_mv)[i]=v' in led
assert 'HAL_UART_Receive_DMA(&huart3' in led
assert '__HAL_DMA_DISABLE_IT(huart3.hdmarx,DMA_IT_HT|DMA_IT_TC|DMA_IT_TE);' in led
assert 'BMS policy=read_only stockREAD30=110ms cells=550ms' in te
assert 'BMS live status=' in te and 'BMS cells=' in te and 'BMS meta sn=' in te

# Exact Stock126 READ30 wire frame.
out=[0x5A,0xA5,0x01,0x20,0x22,0x01,0x30,0x0C,0,0]
ck=(~sum(out[2:8]))&0xffff
out[8]=ck&0xff;out[9]=(ck>>8)&0xff
assert out==[0x5A,0xA5,0x01,0x20,0x22,0x01,0x30,0x0C,0x7F,0xFF]

# Production driver is telemetry-only and isolated from motor observer/protection.
assert 'g30_bms_final_' not in vs
assert 'g30_bms_final_' not in mc
assert 'observer_source=ADC protection_source=ADC' in te

# Entire BMS workstream must keep the hard powerstage lock.
assert 'R3_2_TurnOnLowSides' in r3
assert 'LL_TIM_DisableAllOutputs(TIMx);' in r3
assert 'LL_TIM_CC_IsEnabledChannel(TIMx,TIMxCCER_MASK_CH123) != 0u' in r3
assert r3.count('G30_BMS_BATTERY_SAFE_POWERLOCK') >= 2
assert 'BMSPOWERLOCK enabled=1' in te
assert 'powerstage_locked' in te

print('BMS_FINALREAD_V1_BUILD_ID=PASS')
print('BMS_FINALREAD_V1_115200_ONLY=PASS')
print('BMS_FINALREAD_V1_EXACT_STOCK_READ30=PASS')
print('BMS_FINALREAD_V1_READ_ONLY=PASS')
print('BMS_FINALREAD_V1_STATUS_DECODE=PASS')
print('BMS_FINALREAD_V1_CELL_DECODE=PASS')
print('BMS_FINALREAD_V1_METADATA_DECODE=PASS')
print('BMS_FINALREAD_V1_NO_MOTOR_COUPLING=PASS')
print('BMS_FINALREAD_V1_POWERLOCK_RETAINED=PASS')
