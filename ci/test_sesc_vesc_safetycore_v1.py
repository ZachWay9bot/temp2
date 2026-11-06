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
fo=rd('common_files/src/g30_fo76_shadow.c')
fh=rd('common_files/src/g30_fo76_shadow.h')

# Existing SafetyCore V1 protection contract remains active in V2.
assert 'HW_NAME "SESC-DRV126-POWERCORE6500-SAFETYCORE-V2-HYBRID"' in de
assert '#define G30_VESC_SAFETYCORE_V1 1' in de
assert '#define G30_VESC_SAFETYCORE_V2_HYBRID 1' in de
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

# V2 thermal fix: G30 temperature ADC is inverse, so torque must decrease as raw ADC decreases.
assert 'if(end < start){ float t=start; start=end; end=t; }' in vs
assert 'if(temp <= fp.temp_cut_end || fp.temp_cut_end >= fp.temp_cut_start)' in vs
assert 'utils_map_int(temp, fp.temp_cut_start, fp.temp_cut_end, iq, 0)' in vs
assert 'utils_map_int(temp, fp.temp_cut_start, fp.temp_cut_end, 0, iq)' not in vs

def map_int(x,in_min,in_max,out_min,out_max):
    return int((x-in_min)*(out_max-out_min)/(in_max-in_min)+out_min)

def thermal(raw,start,end,iq):
    if raw < start:
        if raw <= end or end >= start:
            return 0
        return map_int(raw,start,end,iq,0)
    return iq

for iq in (1000,-1000,5000,-5000):
    vals=[thermal(x,40000,30000,iq) for x in (41000,40000,37500,35000,32500,30000,29000)]
    assert vals[0]==iq and vals[1]==iq
    assert vals[-1]==0 and vals[-2]==0
    mags=[abs(v) for v in vals]
    assert all(a>=b for a,b in zip(mags,mags[1:])),(iq,vals)

# V2 hybrid supervisor: Hall starts from standstill and requests FO76 only at the proven forward 64-dpp point.
assert '#define G30_HYBRID_TAKEOVER_MIN_DPP 64' in vs
assert 'hdpp<=-(int16_t)G30_HYBRID_TAKEOVER_MIN_DPP' in vs
assert 'vfr.source==G30_VBUS_SRC_PA1 && vfr.pa1_mv<=45000u' in vs
assert 'g30_fo76_request_takeover(1u);' in vs
assert 'Reverse remains Hall-only for now.' in vs
assert 'VescToSTM_g30_hybrid_supervisor();' in vs

# FO76 still decides whether takeover is valid: request != permission.
assert 'd.valid && d.tracking && takeover_phase_history' in fo
assert 'hall_speed_dpp<=-(int16_t)G30_R3G_TAKEOVER_MIN_DPP' in fo
assert 'abs_phase16(pred_err)<G30_R3G_ENTRY_ERR_COUNTS' in fo

# No live observer->Hall snapback if PA1 trust is lost after observer angle ownership.
assert 'g30_fo76_takeover_owns_angle' in fh and 'g30_fo76_request_coast' in fh
assert 'if(g30_fo76_takeover_owns_angle())' in vs
assert 'if(!vbus_ok) g30_fo76_request_coast();' in vs
assert 'VescToSTM_g30_sensorless_selected() || g30_fo76_takeover_owns_angle()' in mc
assert 'if(g30_fo76_takeover_owns_angle()) g30_fo76_request_coast();' in mc

# Fast coast now protects standalone sensorless and Hall->observer hybrid.
fast=mc[mc.index('#ifdef G30_VESC_SAFETYCORE_V1',mc.index('FOC_CurrControllerM1')):]
assert 'if(g30_fo76_coast_requested())' in fast
assert 'PWMC_SwitchOffPWM(pwmcHandle[M1]);' in fast

# Runtime visibility and intentionally unchanged bench power envelope.
assert 'SAFETYCORE_V2 hybrid_auto=1 tk_dpp=64' in te
assert 'thermal_direction=HOTTER_IS_LOWER' in te
assert 'phase_cmd_mA=5000 abs_trip_mA=10000 speed_erpm=3000' in te
assert '5.0f*CURRENT_FACTOR_A' in mc
assert 'g30_drv126_final_vq,-8192,8192' in mc

def allowed(mode,pa1_v,fault_now,released):
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

def hybrid_arm(hall_selected,hall_valid,dpp,src,pa1_mv,sensorless_ok,owns=False):
    if not hall_selected: return False
    vbus_ok=sensorless_ok and src=='PA1' and pa1_mv<=45000
    if owns: return 'COAST' if not vbus_ok else 'KEEP'
    return vbus_ok and hall_valid and dpp<=-64

hybrid_cases=[
 ((1,1,-63,'PA1',27000,1,0),False),
 ((1,1,-64,'PA1',27000,1,0),True),
 ((1,1,-100,'PA1',44999,1,0),True),
 ((1,1,-100,'PA1',45001,1,0),False),
 ((1,1,-100,'BMS_EST',40000,1,0),False),
 ((1,1,100,'PA1',27000,1,0),False),
 ((1,0,-100,'PA1',27000,1,0),False),
 ((1,1,-100,'PA1',47000,1,1),'COAST'),
]
for args,exp in hybrid_cases:
    got=hybrid_arm(*args)
    assert got==exp,(args,got,exp)

print('SAFETYCORE_V2_SOURCE_CONTRACT=PASS')
print('SAFETYCORE_V2_THERMAL_DIRECTION=PASS')
print('SAFETYCORE_V2_THERMAL_FAILSAFE_CLAMP=PASS')
print('SAFETYCORE_V2_HALL_START_PRESERVED=PASS')
print('SAFETYCORE_V2_HYBRID_64DPP_FORWARD_ONLY=PASS')
print('SAFETYCORE_V2_FO76_CONFIDENCE_GATE_PRESERVED=PASS')
print('SAFETYCORE_V2_PA1_45V_GATE_PRESERVED=PASS')
print('SAFETYCORE_V2_NO_LIVE_SNAPBACK=PASS')
print('SAFETYCORE_V2_FAST_COAST=PASS')
print('SAFETYCORE_V2_POWER_LIMITS_UNCHANGED=PASS')
print('SAFETYCORE_V2_SCENARIO_MATRIX=8/8 PASS')

# CI retrigger: SafetyCore V2 hybrid workflow present on branch.
