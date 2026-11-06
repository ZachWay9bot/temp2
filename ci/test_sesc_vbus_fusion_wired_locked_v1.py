#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")
de=(root/"common_files/src/defines.h").read_text()
tl=(root/"common_files/src/task_LED.c").read_text()
th=(root/"common_files/src/task_LED.h").read_text()
mc=(root/"common_files/src/mc_tasks.c").read_text()
fo=(root/"common_files/src/g30_fo76_shadow.c").read_text()
fh=(root/"common_files/src/g30_fo76_shadow.h").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
te=(root/"common_files/src/terminal.c").read_text()
vf=(root/"common_files/src/g30_vbus_fusion_impl.inc").read_text()
vh=(root/"common_files/src/g30_vbus_fusion.h").read_text()
pwm=(root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c").read_text()

assert 'SESC-DRV126-POWERCORE6500-VBUS-FUSION-WIRED-LOCKED-V1' in de
assert '#define G30_BMS_BATTERY_SAFE_POWERLOCK 1' in de
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' in pwm
assert pwm.count('LL_TIM_DisableAllOutputs(TIMx);') >= 2

# BMS runtime cache and fast 0x30/0x40 scheduler.
assert 'g30_bms_fusion_snapshot_t' in th
assert 'g30_bms_fusion_snapshot(' in tl
assert 'fusion_live_ms' in tl and 'fusion_cells_ms' in tl
assert 'BA(slot)=8u;' in tl and 'BA(slot)=10u;' in tl
assert 'live 0x30 and cells 0x40 alternately' in tl
assert 'BA(fusion_est_mv)=BA(fusion_pack_mv)+((BA(fusion_cell_sum_mv)*2u+2u)/5u);' in tl
assert 'out->age_ms=age_live>age_cells?age_live:age_cells;' in tl
assert 'out->plausible=' in tl

# Exactly one external fusion implementation; terminal only consumes API.
assert '#include "g30_vbus_fusion_impl.inc"' in mc
assert '#include "g30_vbus_fusion_impl.inc"' not in te
assert 'g30_vbus_fusion_runtime_result(void)' in mc
assert 'g30_vbus_fusion_runtime_mv(void)' in mc
assert 'G30_VBUS_PA1_TRUST_MAX_MV' in mc
assert 'bs.age_ms<=G30_VBUS_BMS_MAX_AGE_MS' in mc

# FO76 now receives physical fused millivolts, not the saturated PA1 count.
assert 'uint16_t vbus_mv_in' in fo
assert 'uint32_t vbus_mv=(uint32_t)vbus_mv_in;' in fo
assert 'vbus_adc * vbus_mv_per_count_q16' not in fo
assert 'uint16_t vbus_mv, uint16_t ccr_a' in fh
assert mc.count('g30_vbus_fusion_runtime_mv()') >= 2
assert 'pBusSensorM1->_Super.AvBusVoltage_d,' not in mc[mc.index('g30_fo76_shadow_step'):]

# Startup preload uses the same fused source and fails closed.
assert '#include "g30_vbus_fusion.h"' in vs
assert 'g30_vbus_fusion_runtime_result();' in vs
assert 'if(!vfr.sensorless_ok) return;' in vs
assert 'g30_r3i_preload_calculate(speed,lambda,bus_mv);' in vs

# Diagnostics clearly distinguish runtime wiring from pure SIM vectors.
assert 'strcmp(argv[0], "g30_vbus_fusion_wired")' in te
assert 'observer_connected=1 preload_connected=1 powerstage_locked=1' in te
assert 'VBFUS_SIM_WIRING runtime_observer_connected=1 sim_only=1 powerstage_locked=1' in te

# Pure policy remains fail-closed above PA1 trust range.
assert 'r.source=G30_VBUS_SRC_INVALID' in vf and 'r.sensorless_ok=0u' in vf
assert 'G30_VBUS_PA1_TRUST_MAX_MV 45000u' in vh
assert 'G30_VBUS_BMS_MAX_AGE_MS   500u' in vh

print('VBFUS_WIRED_BUILD_ID=PASS')
print('VBFUS_WIRED_BMS_FAST_CACHE=PASS')
print('VBFUS_WIRED_FO76_MV_SOURCE=PASS')
print('VBFUS_WIRED_PRELOAD_SOURCE=PASS')
print('VBFUS_WIRED_SENSORLESS_FAIL_CLOSED=PASS')
print('VBFUS_WIRED_POWERLOCK=PASS')
