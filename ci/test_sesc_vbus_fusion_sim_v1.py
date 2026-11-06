#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")
de=(root/"common_files/src/defines.h").read_text()
te=(root/"common_files/src/terminal.c").read_text()
fu=(root/"common_files/src/g30_vbus_fusion.c").read_text()
fh=(root/"common_files/src/g30_vbus_fusion.h").read_text()
fo=(root/"common_files/src/g30_fo76_shadow.c").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
pwm=(root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c").read_text()
assert 'SESC-DRV126-POWERCORE6500-VBUS-FUSION-SIM-V1' in de
assert 'G30_VBUS_PA1_TRUST_MAX_MV 45000u' in fh
assert 'G30_VBUS_BMS_MAX_AGE_MS   500u' in fh
assert 'bms_pack_mv + (uint32_t)(((uint64_t)bms_cell_sum_mv*2u + 2u)/5u)' in fu
assert 'g30_absdiff_u32(bms_pack_mv,bms_cell_sum_mv)<=500u' in fu
assert 'r.source=G30_VBUS_SRC_INVALID' in fu and 'r.sensorless_ok=0u' in fu
assert 'strcmp(argv[0], "g30_vbus_fusion_sim")' in te
assert 'observer_connected=0 powerstage_locked=1' in te
assert '#define G30_BMS_BATTERY_SAFE_POWERLOCK 1' in de
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' in pwm
# SIM must not connect fusion into observer or startup preload.
assert 'g30_vbus_fusion' not in fo
assert 'g30_vbus_fusion' not in vs
print('VBFUS_SIM_BUILD_ID=PASS')
print('VBFUS_SIM_FIXED_RATIO_FROM_REAL_CELLS=PASS')
print('VBFUS_SIM_FRESHNESS_AND_PLAUSIBILITY=PASS')
print('VBFUS_SIM_SENSORLESS_FAIL_CLOSED=PASS')
print('VBFUS_SIM_OBSERVER_DISCONNECTED=PASS')
print('VBFUS_SIM_POWERLOCK=PASS')
