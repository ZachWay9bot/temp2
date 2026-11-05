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
	int32_t erpm = VescToSTM_speed_to_erpm(MCI_GetAvrgMecSpeedUnit( pMCI[M1] ));
	return erpm;
}'''
new = '''int32_t VescToSTM_get_erpm(){
#ifdef G30P
	/* SPEEDTEL V1: reporting only. The G30 control path already has a validated
	 * electrical-speed source in hElSpeedDpp (used by get_erpm_fast and the
	 * motorpath audit). The generic MCI average-speed getter can remain zero on
	 * this dual-mode tree. Keep get_erpm_fast itself untouched because it is also
	 * used by control/preload code; only normalize its value for VESC telemetry. */
	int32_t erpm = VescToSTM_get_erpm_fast() * 2;
	return erpm * DIR_MUL;
#else
	int32_t erpm = VescToSTM_speed_to_erpm(MCI_GetAvrgMecSpeedUnit( pMCI[M1] ));
	return erpm;
#endif
}'''
assert old in s, "VescToSTM_get_erpm baseline changed"
s = s.replace(old, new, 1)

old = '''int32_t VescToSTM_get_rpm(){
	int32_t rpm = VescToSTM_speed_to_rpm(MCI_GetAvrgMecSpeedUnit( pMCI[M1] ));
	return rpm;
}'''
new = '''int32_t VescToSTM_get_rpm(){
#ifdef G30P
	return VescToSTM_get_erpm() / (int32_t)VescToSTM_motor_pole_pairs();
#else
	int32_t rpm = VescToSTM_speed_to_rpm(MCI_GetAvrgMecSpeedUnit( pMCI[M1] ));
	return rpm;
#endif
}'''
assert old in s, "VescToSTM_get_rpm baseline changed"
s = s.replace(old, new, 1)

old = '''float VescToSTM_get_speed(void) {
	float pole_pairs = (float)VescToSTM_motor_pole_pairs();
	float temp = (((float)MCI_GetAvrgMecSpeedUnit(pMCI[M1]) / 10.0f) *
				  mc_conf.si_wheel_diameter * 3.14159265359f) /
				 mc_conf.si_gear_ratio / pole_pairs;
	return temp * DIR_MUL;
}'''
new = '''float VescToSTM_get_speed(void) {
#ifdef G30P
	/* SPEEDTEL V1: VescToSTM_get_erpm() is already normalized to the VESC
	 * configured forward direction. Convert electrical RPM to wheel m/s. */
	float pole_pairs = (float)VescToSTM_motor_pole_pairs();
	float mech_rps = ((float)VescToSTM_get_erpm() / 60.0f) / pole_pairs;
	return (mech_rps * mc_conf.si_wheel_diameter * 3.14159265359f) /
		   mc_conf.si_gear_ratio;
#else
	float pole_pairs = (float)VescToSTM_motor_pole_pairs();
	float temp = (((float)MCI_GetAvrgMecSpeedUnit(pMCI[M1]) / 10.0f) *
				  mc_conf.si_wheel_diameter * 3.14159265359f) /
				 mc_conf.si_gear_ratio / pole_pairs;
	return temp * DIR_MUL;
#endif
}'''
assert old in s, "VescToSTM_get_speed baseline changed"
s = s.replace(old, new, 1)

p.write_text(s)
print("SESC POWERCORE6500 SPEEDTEL V1 applied: telemetry source only; motor/control path untouched")
