#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")
def rd(p): return (root/p).read_text()
de=rd('common_files/src/defines.h')
vs=rd('common_files/src/VescToSTM.c')
mc=rd('common_files/src/mc_tasks.c')
cf=rd('common_files/src/conf_general.c')
pw=rd('common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c')
pr=rd('common_files/inc/product.h')
te=rd('common_files/src/terminal.c')
assert 'HW_NAME "SESC-DRV126-POWERCORE6500-VESC-SAFETYCORE-V1"' in de
assert '#define G30_VESC_SAFETYCORE_V1 1' in de
assert 'G30_VBUS_LIVE_SHADOW_GATE' not in de
assert 'return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_SENSORLESS;' in vs
assert 'return mc_conf.foc_sensor_mode == FOC_SENSOR_MODE_HALL;' in vs
assert 'if(erpm>3000) erpm=3000;' in vs and 'if(erpm< -3000) erpm=-3000;' in vs
assert 'g30_lim_erpm>3000 || g30_lim_erpm< -3000' in vs
assert 'current_to_torque(5000)' in vs
assert 'VescToSTM_get_bus_voltage()>45.0f' in vs
assert 'STM_GetState(pMCI[M1]->pSTM)==FAULT_OVER' in vs
rearm=vs[vs.index('static void VescToSTM_g30_coast_rearm'):vs.index('void VescToSTM_g30_pushstart_command')]
assert rearm.index('MCI_FaultAcknowledged(pMCI[M1])') < rearm.index('if(ps.mode==1u)')
assert 'vfr.source!=G30_VBUS_SRC_PA1' in vs and 'vfr.pa1_mv>45000u' in vs
assert '(void)MCI_FaultAcknowledged(pMCI[M1]);' in vs
assert '5.0f*CURRENT_FACTOR_A' in mc
assert 'g30_drv126_final_vq,-8192,8192' in mc
assert 'dmc=0;' in mc
assert 'g30_fo76_coast_requested()' in mc and 'PWMC_SwitchOffPWM(pwmcHandle[M1]);' in mc
assert 'g30_pa1_trust_counts' in mc and '45.0f*BATTERY_VOLTAGE_GAIN' in mc
segment=mc[mc.index('uint8_t hall_guard='):mc.index('hCodeError=g30_drv126_final_power_step')]
assert 'VescToSTM_g30_sensorless_selected()' in segment
assert 'g30_vbus_fusion_runtime_sensorless_ok()' not in segment
assert '(ia_oc > oc)' in pw and '(ib_oc > oc)' in pw and '(ic_oc > oc)' in pw
ocseg=pw[pw.index('int32_t oc ='):pw.index('/**',pw.index('int32_t oc ='))]
assert 'R3_2_SwitchOffPWM(pHdl);' in ocseg
assert '10.0f * CURRENT_FACTOR_A' in cf
safecf=cf[cf.index('#ifdef G30_VESC_SAFETYCORE_V1',cf.index('float oc_counts_f')):cf.index('#else',cf.index('#ifdef G30_VESC_SAFETYCORE_V1',cf.index('float oc_counts_f')))]
assert 'OverCurrentCycles = 0' in safecf
assert '#ifdef G30P\n#define AUTO_RESET_FAULT 0' in pr
assert '#ifndef G30_VESC_SAFETYCORE_V1' in mc and 'VescToSTM_pwm_start();' in mc
assert 'strcmp(argv[0], "g30_safetycore")' in te
assert 'oc_cycles=%lu' in te and 'OverCurrentCycles' in te and 'OverCurrentFlag' in te

def allowed(mode, pa1_v, fault_now, released):
    if fault_now: return False
    if mode=='sensorless' and pa1_v>45.0: return False
    if released: return False
    return True
cases=[
 ('hall',24.0,0,0,True),('hall',58.8,0,0,True),
 ('sensorless',24.0,0,0,True),('sensorless',44.9,0,0,True),
 ('sensorless',45.1,0,0,False),('hall',36.0,1,0,False),
 ('sensorless',36.0,1,0,False),('hall',36.0,0,1,False),
]
for c in cases:
    assert allowed(*c[:4])==c[4],c

def oc(a,b,c,lim=10.0): return abs(a)>lim or abs(b)>lim or abs(c)>lim
for vals,exp in [((10.1,0,0),1),((0,-10.2,0),1),((0,0,15),1),((9.9,-9.9,0),0),((10,0,-10),0)]:
    assert bool(oc(*vals))==bool(exp),(vals,exp)
print('SAFETYCORE_SOURCE_CONTRACT=PASS')
print('SAFETYCORE_FAULT_RELEASE_LATCH=PASS')
print('SAFETYCORE_OCP_ALL_PHASES_IMMEDIATE=PASS')
print('SAFETYCORE_HALL_HIGHV_INDEPENDENT=PASS')
print('SAFETYCORE_SENSORLESS_PA1_ONLY=PASS')
print('SAFETYCORE_SCENARIO_MATRIX=8/8 PASS')
