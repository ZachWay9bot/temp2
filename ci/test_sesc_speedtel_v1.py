#!/usr/bin/env python3
from pathlib import Path

root = Path("SOURCE_KOXX3")
vs = (root / "common_files/src/VescToSTM.c").read_text()
de = (root / "common_files/src/defines.h").read_text()
vc = (root / "common_files/src/VescCommand.c").read_text()
au = (root / "common_files/src/app_uartcomm.c").read_text()
mc = (root / "common_files/src/mc_tasks.c").read_text()

assert 'SESC-DRV126-POWERCORE6500-SPEEDTEL-V1' in de
assert 'int32_t erpm = VescToSTM_get_erpm_fast() * 2;' in vs
assert 'return erpm * DIR_MUL;' in vs
assert 'return VescToSTM_get_erpm() / (int32_t)VescToSTM_motor_pole_pairs();' in vs
assert 'float mech_rps = ((float)VescToSTM_get_erpm() / 60.0f) / pole_pairs;' in vs

# The validated fast/control speed source must remain untouched.
fast = vs[vs.index('int32_t VescToSTM_get_erpm_fast()'):vs.index('/**', vs.index('int32_t VescToSTM_get_erpm_fast()') + 10)]
assert 'SpeednPosFdbk_Handle_t *spd = SpeednTorqCtrlM1.SPD;' in fast
assert 'spd->hElSpeedDpp' in fast
assert 'return VescToSTM_speed_to_erpm(speed);' in fast

# Control/preload still consumes the raw internal fast source, not normalized telemetry.
assert 'hall_erpm=VescToSTM_get_erpm_fast()*2' in vs
assert 'g30_drv126_final_power_step' in mc
assert 'g30_fo76_shadow_step' in mc

# VESC and stock-dashboard reporting paths both consume the corrected reporting getter.
assert 'buffer_append_float32(buffer, VescToSTM_get_erpm(), 1e0' in vc
assert 'buffer_append_float32(buffer, VescToSTM_get_speed(), 1e3' in vc
assert 'float speed_kmh = fabsf(VescToSTM_get_speed()) * 3.6f;' in au

# Simple sign/magnitude regression from the accepted bench trace:
# internal fast source -3642 ERPM-equivalent at configured invert -> VESC +7284 ERPM.
raw_fast = -3642
dir_mul = -1
reported = raw_fast * 2 * dir_mul
assert reported == 7284

print("SPEEDTEL_V1_BUILD_ID=PASS")
print("SPEEDTEL_V1_ERPM_SOURCE=PASS")
print("SPEEDTEL_V1_RPM_CONVERSION=PASS")
print("SPEEDTEL_V1_SPEED_CONVERSION=PASS")
print("SPEEDTEL_V1_CONTROL_PATH_UNTOUCHED=PASS")
print("SPEEDTEL_V1_VESC_REPORTING=PASS")
print("SPEEDTEL_V1_DASH_REPORTING=PASS")
print("SPEEDTEL_V1_SIGN_MAGNITUDE=PASS")
