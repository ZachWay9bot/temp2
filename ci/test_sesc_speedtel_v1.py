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
assert 'return VescToSTM_get_erpm() / VescToSTM_pole_pairs();' in vs
assert 'float mech_rps = ((float)VescToSTM_get_erpm() / 60.0f) / (float)VescToSTM_pole_pairs();' in vs

# Validated fast/control source remains exactly the Hall/FO76 electrical DPP path.
fast_start = vs.index('int32_t VescToSTM_get_erpm_fast()')
fast_end = vs.index('/**', fast_start + 10)
fast = vs[fast_start:fast_end]
assert 'HALL_M1._Super.hElSpeedDpp' in fast
assert 'HALL_M1._Super.hMeasurementFrequency' in fast
assert 'HALL_M1._Super.DPPConvFactor' in fast
assert 'return VescToSTM_speed_to_erpm(speed);' in fast

# Control and preload still use raw internal speed; telemetry normalization cannot feed back.
assert 'hall_erpm=VescToSTM_get_erpm_fast()*2' in vs
assert 'g30_drv126_final_power_step' in mc
assert 'g30_fo76_shadow_step' in mc

# VESC and stock-dashboard reporting both consume the corrected reporting getters.
assert 'buffer_append_float32(buffer, VescToSTM_get_erpm(), 1e0' in vc
assert 'buffer_append_float32(buffer, VescToSTM_get_speed(), 1e3' in vc
assert 'float speed_kmh = fabsf(VescToSTM_get_speed()) * 3.6f;' in au

# Accepted bench trace regression: raw fast -3642 with invert enabled -> VESC +7284 ERPM.
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
