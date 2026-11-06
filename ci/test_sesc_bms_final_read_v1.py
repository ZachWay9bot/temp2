#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")
de=(root/"common_files/src/defines.h").read_text()
led=(root/"common_files/src/task_LED.c").read_text()
hdr=(root/"common_files/src/task_LED.h").read_text()
te=(root/"common_files/src/terminal.c").read_text()
msp=(root/"g30p/Src/stm32f1xx_hal_msp.c").read_text()
r3=(root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c").read_text()

assert 'SESC-DRV126-POWERCORE6500-BMS-FINAL-READ-V1' in de
assert '#define G30_BMS_BATTERY_SAFE_POWERLOCK 1' in de
assert 'G30_BMS_AUDIT_SLOTS 19u' in led
assert '0x00u,0x10u,0x17u,0x18u,0x19u,0x1Bu,0x1Cu,0x20u,0x30u,0x3Bu' in led
assert '0x40u,0x51u,0x70u,0x31u,0x32u,0x33u,0x34u,0x35u,0x36u' in led
assert '2u,14u,2u,2u,2u,2u,2u,2u,14u,2u,20u,2u,12u' in led
assert 'huart3.Init.BaudRate=115200u' in led
assert '76800' not in led[led.index('G30 BMS FINAL READ V1'):led.index('void prv_LED_blink',led.index('G30 BMS FINAL READ V1'))]
assert 'g30_bms_audit_parse_byte' in led
assert 'BA(src)==0x22u && BA(dst)==0x20u && BA(cmd)==0x04u' in led
assert 'BMSFINAL round=' in te
assert 'BMSID magic=' in te and 'BMSLIVE status=' in te and 'BMSCELLS ' in te and 'BMSCROSS ' in te
assert 'BMSPOWERLOCK enabled=1' in te
assert 'no_bms_write Cpin_untouched powerstage_locked' in te
assert 'GPIO_SPEED_FREQ_HIGH' in msp
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' in r3
assert r3.count('LL_TIM_DisableAllOutputs(TIMx);') >= 2
# V2 scan must not be part of final-read V1.
assert 'g30_bms_scan' not in te
assert 'scan_data[128][2]' not in led
assert 'BASCAN_SUM' not in te
print('BMS_FINAL_READ_V1_BUILD_ID=PASS')
print('BMS_FINAL_READ_V1_115200_ONLY=PASS')
print('BMS_FINAL_READ_V1_SEMANTIC_MAP=PASS')
print('BMS_FINAL_READ_V1_NO_SWEEP=PASS')
print('BMS_FINAL_READ_V1_POWERLOCK=PASS')
print('BMS_FINAL_READ_V1_READ_ONLY=PASS')
