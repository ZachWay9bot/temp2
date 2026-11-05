#!/usr/bin/env python3
from pathlib import Path

root = Path("SOURCE_KOXX3")

p = root / "common_files/src/defines.h"
s = p.read_text()
old = '#define HW_NAME "SESC-DRV126-POWERCORE6500-FINAL-V1"'
new = '#define HW_NAME "SESC-DRV126-POWERCORE6500-SPEEDTEL-V1"'
assert old in s, "expected POWERCORE6500 FINAL V1 build id not found"
p.write_text(s.replace(old, new, 1))

p = root / "common_files/src/VescToSTM.c"
s = p.read_text()

old = '''int32_t VescToSTM_get_erpm(){
\tint32_t erpm = VescToSTM_speed_to_erpm(MCI_GetAvrgMecSpeedUnit( pMCI[M1] ));
\treturn erpm;
}'''
new = '''int32_t VescToSTM_get_erpm(){
#ifdef G30P
\t/* SPEEDTEL V1: reporting only. Reuse the validated electrical-speed source
\t * already used by the accepted motorpath diagnostics. Keep get_erpm_fast()
\t * itself untouched because Hall preload/control code also consumes it. */
\tint32_t erpm = VescToSTM_get_erpm_fast() * 2;
\treturn erpm * DIR_MUL;
#else
\tint32_t erpm = VescToSTM_speed_to_erpm(MCI_GetAvrgMecSpeedUnit( pMCI[M1] ));
\treturn erpm;
#endif
}'''
assert old in s, "VescToSTM_get_erpm baseline changed"
s = s.replace(old, new, 1)

old = '''int32_t VescToSTM_get_rpm(){
\tint32_t rpm = VescToSTM_speed_to_rpm(MCI_GetAvrgMecSpeedUnit( pMCI[M1] ));
\treturn rpm;
}'''
new = '''int32_t VescToSTM_get_rpm(){
#ifdef G30P
\treturn VescToSTM_get_erpm() / VescToSTM_pole_pairs();
#else
\tint32_t rpm = VescToSTM_speed_to_rpm(MCI_GetAvrgMecSpeedUnit( pMCI[M1] ));
\treturn rpm;
#endif
}'''
assert old in s, "VescToSTM_get_rpm baseline changed"
s = s.replace(old, new, 1)

old = '''float VescToSTM_get_speed(void) {
\tfloat temp = (((float)MCI_GetAvrgMecSpeedUnit(pMCI[M1]) / 10.0) * mc_conf.si_wheel_diameter * M_PI) / mc_conf.si_gear_ratio / (float)VescToSTM_pole_pairs();
\treturn temp * DIR_MUL;
}'''
new = '''float VescToSTM_get_speed(void) {
#ifdef G30P
\t/* SPEEDTEL V1: reported ERPM is already normalized to configured VESC FWD. */
\tfloat mech_rps = ((float)VescToSTM_get_erpm() / 60.0f) / (float)VescToSTM_pole_pairs();
\treturn (mech_rps * mc_conf.si_wheel_diameter * M_PI) / mc_conf.si_gear_ratio;
#else
\tfloat temp = (((float)MCI_GetAvrgMecSpeedUnit(pMCI[M1]) / 10.0) * mc_conf.si_wheel_diameter * M_PI) / mc_conf.si_gear_ratio / (float)VescToSTM_pole_pairs();
\treturn temp * DIR_MUL;
#endif
}'''
assert old in s, "VescToSTM_get_speed baseline changed"
s = s.replace(old, new, 1)

p.write_text(s)
print("SESC POWERCORE6500 SPEEDTEL V1 applied: telemetry source only; motor/control path untouched")
