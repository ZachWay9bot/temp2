#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")
de=(root/"common_files/src/defines.h").read_text()
tl=(root/"common_files/src/task_LED.c").read_text()
th=(root/"common_files/src/task_LED.h").read_text()
mc=(root/"common_files/src/mc_tasks.c").read_text()
te=(root/"common_files/src/terminal.c").read_text()
vf=(root/"common_files/src/g30_vbus_fusion_impl.inc").read_text()
vh=(root/"common_files/src/g30_vbus_fusion.h").read_text()
pwm=(root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c").read_text()

assert 'SESC-DRV126-POWERCORE6500-VBUS-FUSION-WIRED-LOCKED-V2' in de
assert '#define G30_BMS_BATTERY_SAFE_POWERLOCK 1' in de
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' in pwm

assert 'bms_cells_age_ms' in vh
assert 'live_age_ms' in th and 'cells_age_ms' in th
assert 'out->live_age_ms=age_live;' in tl
assert 'out->cells_age_ms=age_cells;' in tl
assert 'BA(fusion_est_mv)=(BA(fusion_pack_mv)*14u+5u)/10u;' in tl
assert 'BA(wait_ticks)=18u' in tl
assert 'fusion_poll_phase' in tl
assert 'BA(fusion_poll_phase)=1u;' in tl
assert 'BA(fusion_poll_phase)=2u;' in tl
assert 'BA(slot)=10u;' in tl

assert 'r.est_mv=(uint32_t)((bms_pack_mv*14u + 5u)/10u);' in vf
assert 'bs.live_age_ms<=G30_VBUS_BMS_MAX_AGE_MS' in mc
assert 'bs.cells_age_ms<=1500u' in mc
assert 'r.bms_cells_age_ms=bs.cells_age_ms;' in mc
assert 'cage=%lu' in te
assert 'policy=pack14over10' in te

# Wiring from V1 must remain.
assert mc.count('g30_vbus_fusion_runtime_mv()') >= 2
assert 'g30_vbus_fusion_runtime_result();' in (root/"common_files/src/VescToSTM.c").read_text()
assert 'uint32_t vbus_mv=(uint32_t)vbus_mv_in;' in (root/"common_files/src/g30_fo76_shadow.c").read_text()

print('VBFUS_V2_BUILD_ID=PASS')
print('VBFUS_V2_LIVE_PACK_14_OVER_10=PASS')
print('VBFUS_V2_30_30_40_SCHEDULER=PASS')
print('VBFUS_V2_SPLIT_FRESHNESS=PASS')
print('VBFUS_V2_OBSERVER_PRELOAD_WIRING=PASS')
print('VBFUS_V2_POWERLOCK=PASS')
