#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")
de=(root/"common_files/src/defines.h").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
mc=(root/"common_files/src/mc_tasks.c").read_text()
te=(root/"common_files/src/terminal.c").read_text()
pr=(root/"common_files/inc/product.h").read_text()
led=(root/"common_files/src/task_LED.c").read_text()
pwm=(root/"common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c").read_text()
fo=(root/"common_files/src/g30_fo76_shadow.c").read_text()
vc=(root/"common_files/src/VescCommand.c").read_text()
assert 'uint8_t send_buffer[PACKET_SIZE(96)];' in vc
assert 'uint8_t send_buffer[PACKET_SIZE(60)];' not in vc
assert 3 + len('SESC-DRV126-POWERCORE6500-FAULTGUARD-V1C') + 1 + 12 + 1 + 1 + 1 + 4 <= 96

assert 'SESC-DRV126-POWERCORE6500-FAULTGUARD-V1C' in de
assert '#define G30_VBUS_LIVE_SHADOW_GATE 1' in de
assert '#define G30_FAULTGUARD_V1 1' in de
assert '#define G30_FAULTGUARD_V1B 1' in de
assert '#define G30_FAULTGUARD_V1C_DIAG 1' in de
assert '#define AUTO_RESET_FAULT\t\t\t\t\t\t\t\t\t\t\t\t\t 0' in pr or '#define AUTO_RESET_FAULT' in pr and pr.split('AUTO_RESET_FAULT',1)[1].lstrip().startswith('0')
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' not in de
assert 'G30_BMS_BATTERY_SAFE_POWERLOCK' in pwm  # dormant guarded code still present

assert '#ifdef G30_VBUS_LIVE_SHADOW_GATE\n    return false;' in vs
assert '#ifdef G30_VBUS_LIVE_SHADOW_GATE\n    return true;' in vs
assert 'if(erpm>3000) erpm=3000;' in vs and 'if(erpm< -3000) erpm=-3000;' in vs

assert '5.0f*CURRENT_FACTOR_A' in mc
assert 'dmc=0;' in mc
assert 'g30_drv126_final_vq,-8192,8192' in mc
assert 'if(!g30_vbus_fusion_runtime_sensorless_ok())' in mc
assert 'PWMC_SwitchOffPWM(pwmcHandle[M1]);' in mc
assert 'g30_fo76_request_takeover(0u);' in mc
assert mc.count('g30_vbus_fusion_runtime_mv()') >= 3
assert 'g30_fo76_shadow_step' in mc

assert 'strcmp(argv[0], "g30_live_shadow_gate")' in te
assert 'hall_forced=1 takeover=0 phase_limit_mA=5000 speed_limit_erpm=3000' in te

assert 'uint32_t vbus_mv=(uint32_t)vbus_mv_in;' in fo

print('LIVE_SHADOW_BUILD_ID=PASS')
print('LIVE_SHADOW_HALL_FORCED=PASS')
print('LIVE_SHADOW_SENSORLESS_TAKEOVER_DISABLED=PASS')
print('LIVE_SHADOW_PHASE_CURRENT_5A_CLAMP=PASS')
print('LIVE_SHADOW_SPEED_3000_ERPM_CLAMP=PASS')
print('LIVE_SHADOW_VOLTAGE_VECTOR_CLAMP=PASS')
print('LIVE_SHADOW_FUSION_FAIL_COAST=PASS')
print('LIVE_SHADOW_FO76_OBSERVER_WIRED=PASS')

print('LIVE_SHADOW_FW_VERSION_BOUNDS=PASS')

assert 'strcmp(argv[0], "g30_faultguard")' in te
assert 'auto_reset=0' in te
assert 'hFaultNow' in te and 'hFaultOccurred' in te
assert 'last_fault_time = 0xFFFFFFFFu' in led
assert 'faults & MC_BREAK_IN' in vs
assert 'return faults ? FAULT_CODE_DRV : FAULT_CODE_NONE;' in vs
print('FAULTGUARD_AUTO_RESET_DISABLED=PASS')
print('FAULTGUARD_RAW_MCSDK_FAULTS=PASS')
print('FAULTGUARD_ONE_SHOT_FAULT_PRINT=PASS')
print('FAULTGUARD_UNKNOWN_MCSDK_FAULT_SURFACED_AS_DRV=PASS')

assert 'strcmp(argv[0], "g30_faultguard_ack")' in te
assert 'FAULTGUARD_ACK DENIED' in te
assert 'MCI_FaultAcknowledged' in te
assert 'st!=FAULT_OVER' in te
assert '!pwm_off || moe' in te
print('FAULTGUARD_SAFE_ACK=PASS')

ack=te.split('strcmp(argv[0], "g30_faultguard_ack")',1)[1].split('}else if',1)[0]
assert 'STM[M1].bState = RUN;' in ack
assert 'pMCI[M1]->pFOCVars->cycles_max = 0u;' in ack
assert 'MCI_ExecSpeedRamp(pMCI[M1],0,0);' in ack
assert 'VescToSTM_pwm_stop();' in ack
assert 'VescToSTM_pwm_start();' not in ack
assert 'ready=RUN' in ack
print('FAULTGUARD_V1B_RUN_PWM_OFF_RECOVERY=PASS')
print('FAULTGUARD_V1B_NO_RECALIBRATION_STATE_MACHINE_ENTRY=PASS')

assert 'cycles_max*100u/(CPU_CLOCK/PWM_FREQUENCY)' in te
print('FAULTGUARD_V1B_FOC_LOAD_DIAG_NO_OVERFLOW=PASS')

assert 'g30_focdur_ch4_count++' in pwm
assert 'g30_focdur_swerr_count++' in pwm
assert 'strcmp(argv[0], "g30_focdur_diag")' in te
assert 'FOCDUR ch4=' in te
print('FAULTGUARD_V1C_FOCDUR_CAUSE_LATCH=PASS')
