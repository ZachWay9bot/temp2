#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")

de=(root/"common_files/src/defines.h").read_text()
te=(root/"common_files/src/terminal.c").read_text()
pr=(root/"common_files/inc/product.h").read_text()
defs=(root/"common_files/src/defines.h").read_text()
cg=(root/"common_files/src/conf_general.c").read_text()
mc=(root/"common_files/src/mc_tasks.c").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
fo=(root/"common_files/src/g30_fo76_shadow.c").read_text()
mcf=(root/"common_files/src/mc_config.c").read_text()
main=(root/"g30p/Src/main.c").read_text()
pwm=(root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c").read_text()

assert 'SESC-DRV126-POWERCORE6500-VBUS-AUDIT-V1' in de
assert '#define G30_BMS_BATTERY_SAFE_POWERLOCK 1' in de
assert 'strcmp(argv[0], "g30_vbus_audit")' in te
assert 'strcmp(argv[0], "g30_powerlock")' in te
assert 'POWERLOCK enabled=1' in te
assert 'VOLTAGE_DIVIDER_GAIN' in pr and '(float)3363.5' in pr
assert '#define ADC_GAIN (float)(3.3 / 4095.0)' in defs
assert 'BATTERY_VOLTAGE_GAIN' in pr and '* 512.0' in pr
assert 'conf_general_bus_voltage_limit_counts' in cg
assert 'utils_truncate_number(&counts, 0.0f, (float)UINT16_MAX);' in cg
assert '.ConversionFactor    = (uint16_t)(BATTERY_VOLTAGE_GAIN)' in mcf
assert 'hadc1.Init.DataAlign = ADC_DATAALIGN_LEFT;' in main

# Hall / DRV126 current-control core has no direct bus-voltage term.
start=mc.index('static uint16_t g30_drv126_final_power_step')
end=mc.index('#endif',start)
hall_core=mc[start:end]
assert 'VBS_Get' not in hall_core and 'VescToSTM_get_bus_voltage' not in hall_core
assert 'BATTERY_VOLTAGE_GAIN' not in hall_core
assert 'g30_drv126_final_pi' in hall_core and 'g30_drv126_final_svpwm' in hall_core

# Sensorless observer and preload explicitly consume the same PA1-derived bus voltage.
assert 'uint32_t vbus_mv=((uint32_t)vbus_adc * vbus_mv_per_count_q16)>>16;' in fo
assert 'valpha=(int32_t)(((int32_t)vbus_mv*ab_n)' in fo
assert 'vbeta=(int32_t)(((int32_t)vbus_mv*' in fo
assert '(uint32_t)(65536000.0f / BATTERY_VOLTAGE_GAIN + 0.5f)' in cg
assert 'pBusSensorM1->_Super.AvBusVoltage_d' in mc
assert 'float bus_v=VescToSTM_get_bus_voltage();' in vs
assert 'g30_r3i_preload_calculate(speed,lambda,bus_mv);' in vs

# Hard lock from the BMS safety layer remains mandatory in this diagnostic build.
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' in pwm
assert pwm.count('LL_TIM_DisableAllOutputs(TIMx);') >= 2

# No Vbus calibration, observer algorithm or power-core constants are patched by apply script itself.
apply=Path('ci/apply_sesc_vbus_audit_v1.py').read_text()
assert 'product.h' not in apply
assert 'g30_fo76_shadow.c' not in apply
assert 'mc_tasks.c' not in apply
assert 'VescToSTM.c' not in apply
assert 'mc_config.c' not in apply
assert 'main.c' not in apply

gain=3363.5*(3.3/4095.0)*512.0
fs=65535.0/gain
assert 47.0 < fs < 47.5
assert 56.0*gain > 65535.0

print(f'VBUS_GAIN_COUNTS_PER_V={gain:.6f}')
print(f'VBUS_U16_FULLSCALE_V={fs:.6f}')
print(f'VBUS_56V_REQUIRED_COUNTS={56.0*gain:.1f}')
print('VBUS_AUDIT_V1_BUILD_ID=PASS')
print('VBUS_AUDIT_V1_PA1_SCALE=PASS')
print('VBUS_AUDIT_V1_OV_CLIP_STATIC=PASS')
print('VBUS_AUDIT_V1_HALL_INNER_NO_VBUS=PASS')
print('VBUS_AUDIT_V1_SENSORLESS_USES_PA1_VBUS=PASS')
print('VBUS_AUDIT_V1_POWERLOCK=PASS')
print('VBUS_AUDIT_V1_DIAGNOSTIC_ONLY=PASS')
