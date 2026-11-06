#!/usr/bin/env python3
from pathlib import Path
import hashlib,re
root=Path('SOURCE_KOXX3')

def sha(rel):
    return hashlib.sha256((root/rel).read_bytes()).hexdigest()

expected={
 'common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c':'14ccd029244f230d5632f18c6c278aa3021976ede8a4513939af068456eee276',
 'common_files/src/mc_tasks.c':'1c3f61ad12855960ddf25ea96730328bdfaa4d8653d6f7ec9fe89d2114518c98',
 'common_files/src/g30_fo76_shadow.c':'cec66fd9085dc363e02cb1b9220b44c7ed643e0f28563782c20f19d5af3ba09b',
 'common_files/src/g30_fo76_shadow.h':'d4c7d026b42dc8165becb6a7665e33d3169d68fb254844cc6214b0975f91966e',
 'g30p/Src/stm32f1xx_hal_msp.c':'8dbb459a398c7fb762d2b47f57f61bdef371b8be7fe340ad038e91d189e5c2e1',
 'common_files/src/VescCommand.c':'37529378ba56e3315d7fff5d4bfd20b2771eacaccaa8e3247329943d1d6a50f9',
}
for rel,want in expected.items():
    got=sha(rel)
    assert got==want,(rel,got,want)
    print(f'EXACT_BASELINE {rel}=PASS {got}')

mc=(root/'common_files/src/mc_tasks.c').read_text()
pwm=(root/'common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c').read_text()
led=(root/'common_files/src/task_LED.c').read_text()
de=(root/'common_files/src/defines.h').read_text()
vs=(root/'common_files/src/VescToSTM.c').read_text()
te=(root/'common_files/src/terminal.c').read_text()
pr=(root/'common_files/inc/product.h').read_text()

for bad in ['g30_vbus_fusion_runtime','g30_bmsphy_hf_sample','G30_VBUS_LIVE_SHADOW_GATE']:
    assert bad not in mc,bad
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' not in pwm
assert 'g30_bms_service_10ms' not in led
assert 'G30_VBUS_LIVE_SHADOW_GATE' not in de
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' not in de
assert 'SESC-DRV126-POWERCORE6500-POWERPATH-RESTORE-V1' in de
assert '#define G30_POWERPATH_RESTORE_V1 1' in de
assert re.search(r'#define AUTO_RESET_FAULT\s+0',pr)
assert 'return false;' in vs.split('bool VescToSTM_g30_sensorless_selected(void){',1)[1].split('}',1)[0]
assert 'return true;' in vs.split('bool VescToSTM_g30_hall_selected(void){',1)[1].split('}',1)[0]
assert 'strcmp(argv[0], "g30_faultguard_ack")' in te
ack=te.split('strcmp(argv[0], "g30_faultguard_ack")',1)[1].split('}else if',1)[0]
assert 'STM[M1].bState = RUN;' in ack
assert 'VescToSTM_pwm_stop();' in ack
assert 'VescToSTM_pwm_start();' not in ack

print('NO_BMS_HF_SAMPLER=PASS')
print('NO_VBUS_FUSION_IN_MOTORPATH=PASS')
print('NO_POWERLOCK=PASS')
print('NO_BMS_LED_SERVICE=PASS')
print('HALL_TEST_SELECTION=PASS')
print('FAULT_LATCH_SAFE_ACK=PASS')
print('POWERPATH_RESTORE_STATIC=PASS')
