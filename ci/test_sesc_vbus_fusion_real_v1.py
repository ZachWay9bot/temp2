#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")
de=(root/"common_files/src/defines.h").read_text()
te=(root/"common_files/src/terminal.c").read_text()
tl=(root/"common_files/src/task_LED.c").read_text()
th=(root/"common_files/src/task_LED.h").read_text()
fo=(root/"common_files/src/g30_fo76_shadow.c").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
pwm=(root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c").read_text()
assert 'SESC-DRV126-POWERCORE6500-VBUS-FUSION-REAL-V1' in de
assert 'uint32_t live_ok_ms;' in tl and 'uint32_t cells_ok_ms;' in tl
assert 'if(sl==8u) BA(live_ok_ms)=HAL_GetTick();' in tl
assert 'if(sl==10u) BA(cells_ok_ms)=HAL_GetTick();' in tl
for n in ['g30_bms_fusion_data_valid','g30_bms_fusion_age_ms','g30_bms_fusion_pack_mv',
          'g30_bms_fusion_cell_sum_mv','g30_bms_fusion_cell_min_mv','g30_bms_fusion_cell_max_mv']:
    assert n in tl and n in th
assert 'strcmp(argv[0], "g30_vbus_fusion_real")' in te
assert 'observer_connected=0 preload_connected=0 powerstage_locked=1' in te
assert 'Cpin_untouched no_bms_write' in te
assert '#define G30_BMS_BATTERY_SAFE_POWERLOCK 1' in de
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' in pwm
# This validation build must still not feed fusion into control.
assert 'g30_vbus_fusion_eval' not in fo
assert 'g30_vbus_fusion_eval' not in vs
print('VBFUS_REAL_BUILD_ID=PASS')
print('VBFUS_REAL_BMS_FRESHNESS=PASS')
print('VBFUS_REAL_PACK_AND_CELL_API=PASS')
print('VBFUS_REAL_OBSERVER_DISCONNECTED=PASS')
print('VBFUS_REAL_POWERLOCK=PASS')
