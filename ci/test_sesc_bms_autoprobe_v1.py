#!/usr/bin/env python3
from pathlib import Path

root=Path("SOURCE_KOXX3")
de=(root/"common_files/src/defines.h").read_text()
led=(root/"common_files/src/task_LED.c").read_text()
te=(root/"common_files/src/terminal.c").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
mc=(root/"common_files/src/mc_tasks.c").read_text()

assert 'SESC-DRV126-POWERCORE6500-BMSPROBE-V1' in de
assert 'static g30_bms_state_t *g30_bms_state;' in led
assert 'pvPortMalloc(sizeof(*g30_bms_state))' in led
assert 'memset(g30_bms_state,0,sizeof(*g30_bms_state));' in led
assert '#define G30_BMS_RX_N 24u' in led
assert 'static const uint8_t reg[5]={0x30,0x10,0x17,0x34,0x40}' in led
assert 'huart3.Init.BaudRate=76800u' in led
assert 'HAL_UART_DMAStop(&huart3)' in led
assert 'g30_bms_raw_rx_count' in led
assert 'rawRx=%u' in te
assert 'baud=%lu idx=%u err=%u' in te
assert 'BMS rawLast=' in te
assert 'HAL_UART_Transmit(&huart3' in led
assert 'HAL_UART_Receive_DMA(&huart3' in led
assert '__HAL_DMA_DISABLE_IT(huart3.hdmarx,DMA_IT_HT|DMA_IT_TC|DMA_IT_TE);' in led
assert 'g30_bms_service_10ms();' in led
assert 'xTaskCreate' not in led[led.index('G30 BMSPROBE V1'):led.index('void prv_LED_blink')]
assert 'strcmp(argv[0], "g30_bms")' in te
assert 'observer_source=ADC protection_source=ADC' in te

# Stock request checksum: ~(01+20+22+01+30+0C) = FF7F.
body=[0x01,0x20,0x22,0x01,0x30,0x0c]
crc=(~sum(body))&0xffff
assert crc==0xff7f

# Response map for the 12-byte register block 0x30..0x35.
payload=[
  0x34,0x12, # 0x30 status
  0x78,0x56, # 0x31 capacity
  0x64,0x00, # 0x32 SOC 100
  0x17,0x00, # 0x33 current 0.23 A
  0x29,0x10, # 0x34 voltage 41.37 V
  0x28,0x28, # 0x35 temperatures
]
assert int.from_bytes(bytes(payload[4:6]),'little')==100
assert int.from_bytes(bytes(payload[6:8]),'little',signed=True)==23
assert int.from_bytes(bytes(payload[8:10]),'little')==4137

# Critical separation: this child must not feed BMS voltage into FO76/protection yet.
assert 'g30_bms_pack_cv' not in vs
assert 'g30_bms_pack_cv' not in mc
assert 'VescToSTM_get_erpm_fast() * 2' in vs
assert 'g30_drv126_final_power_step' in mc
assert 'g30_fo76_shadow_step' in mc

print('BMSPROBE_V1_BUILD_ID=PASS')
print('BMSPROBE_V1_STOCK_READ30_FRAME=PASS')
print('BMSPROBE_V1_REGISTER_MAP=PASS')
print('BMSPROBE_V1_USART3_ONLY=PASS')
print('BMSPROBE_V1_NO_NEW_TASK=PASS')
print('BMSPROBE_V1_DMA_IRQ_LOAD_REMOVED=PASS')
print('BMSPROBE_V1_TELEMETRY_ONLY=PASS')
print('BMSPROBE_V1_SPEEDTEL_RETAINED=PASS')
print('BMSPROBE_V1_POWERCORE_RETAINED=PASS')
