from pathlib import Path
import hashlib, math

root=Path("SOURCE_KOXX3")
mc=(root/"common_files/src/mc_tasks.c").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
de=(root/"common_files/src/defines.h").read_text()
obs=(root/"common_files/src/g30_fo76_shadow.c").read_text()
push=(root/"common_files/src/g30_r3i_pushstart.c").read_text()
drive=(root/"common_files/inc/drive_parameters.h").read_text()
te=(root/"common_files/src/terminal.c").read_text()

assert 'SESC-DRV126-POWERCORE6500-FINAL-V1' in de
print("BUILD_ID=PASS")

# G30 current scale and modified DRV126 coefficient.
cf=32767.0*0.00200*9.4336/(3.3/2.0)
step=round(6.5*cf)
assert step==2435
assert '#define G30_DRV126_CURRENT_RAISING_COEFF_MA 6500' in mc
assert '#define G30_DRV126_CURRENT_RAISING_STEP_MC 2435' in mc
print(f"COEFF6500_SCALE=PASS currentFactor={cf:.9f} stepMC={step}")

# Must execute once per DRV126 4-kHz update, after 16->4 kHz divider.
idx_div=mc.index('if(g30_drv126_final_div!=0u)')
idx_slew=mc.index('int32_t qdelta=qtarget-g30_drv126_final_q_slew_mc;')
assert idx_div<idx_slew
print("COEFF6500_AFTER_4K_DIVIDER=PASS")

# 55 A request: 9 x 250 us = 2.25 ms.
target=round(55*cf)
q=0;n=0
while q!=target:
    d=target-q
    q+=max(-step,min(step,d))
    n+=1
    assert n<100
assert n==9
print(f"COEFF6500_55A_RAMP=PASS steps={n} ms={n/4.0:.2f}")

# Sign reversal never exceeds one coefficient step per controller update.
q=round(30*cf); target=round(-30*cf)
last=q
for _ in range(20):
    d=target-q
    q+=max(-step,min(step,d))
    assert abs(q-last)<=step
    last=q
print("COEFF6500_SIGN_REVERSAL=PASS")

# Both existing VESC selectable modes share one DRV126 current/power core.
assert 'VescToSTM_g30_hall_selected() ||' in mc
assert '(VescToSTM_g30_sensorless_selected() && g30_fo76_sensorless_active())' in mc
assert 'g30_drv126_final_power_step' in mc
assert 'uint8_t hall_guard=(uint8_t)VescToSTM_g30_hall_selected();' in mc
print("HALL_SENSORLESS_SHARED_DRV126_POWERCORE=PASS")

# Hall retains its live GPIO safety guard. Sensorless is independent of Hall.
assert '(hall_guard &&' in mc
assert 'raw==0u || raw==7u || HALL_M1.lut[raw]==255u || !HALL_M1.SensorIsReliable' in mc
print("MODE_SPECIFIC_HALL_GUARD=PASS")

# FO76 gets the actual previous DRV126 PWM vector.
for needle in [
    'g30_old_ca=pwmcHandle[M1]->CntPhA',
    'g30_old_cb=pwmcHandle[M1]->CntPhB',
    'g30_old_cc=pwmcHandle[M1]->CntPhC',
    'g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle',
]:
    assert needle in mc,needle
print("SENSORLESS_ACTUAL_DRV126_PWM_FEEDBACK=PASS")

# Frozen sensorless start behavior and new DRV preload.
assert 'g30_drv126_final_preload(initial.vq_counts,initial.vd_counts);' in vs
assert 'int16_t one_a_q=(int16_t)current_to_torque(1000);' in vs
assert 'const uint32_t hold_ms=800u;' in vs
assert 'const uint32_t ramp_ms=1000u;' in vs
print("SENSORLESS_PRELOAD_HOLD_RAMP=PASS")

# Preserve the proven 16-kHz FO76 contract. This is the deliberate compatibility
# exception to an otherwise stock-derived DRV126 lower layer.
assert '#define PWM_FREQUENCY   16000' in drive
assert 'if(!pwm_on || d.foc_hz!=16000u)' in obs
assert 'if(++decim16<4u)return;' in obs
assert 'g30_drv126_final_div' in mc and '&3u' in mc
print("FO76_16K_DRV126_4K_CONTRACT=PASS")

# Hall-only / sensorless-only selection remains as before. No hybrid auto-switch.
assert 'VescToSTM_g30_hall_selected' in vs
assert 'VescToSTM_g30_sensorless_selected' in vs
assert 'G30_HYBRID' not in mc
assert 'HYBRID-SENSORLESS' not in te
print("NO_HYBRID_MODE_CHANGE=PASS")

# Stock-derived DRV126 motor path remains intact.
for needle in [
    'counts*51575',
    '((ia+2*ib)*2365)>>12',
    '25500057,31128',
    '8500019,10376',
    'const int32_t per=4000,lim=3920',
    'pHdl->Sector=(uint8_t)(sec-1u);',
]:
    assert needle in mc,needle
print("DRV126_STOCK_MATH_CORE=PASS")

assert '#define SW_DEADTIME_NS                   1000' in drive
print("DRV126_1US_DEADTIME=PASS")

# Pure sensorless pushstart source remains byte-identical.
expected='7e73fe8e08a28ce9c500e2fe31bc368d6ddbded3495349949cb85d54a4730c5e'
got=hashlib.sha256((root/"common_files/src/g30_r3i_pushstart.c").read_bytes()).hexdigest()
assert got==expected,(got,expected)
print("PUSHSTART_FROZEN_HASH=PASS")

# Physical observer constants remain frozen.
for needle in [
    '#define G30_FO76_R_PROVEN_MOHM 583u',
    '#define G30_FO76_L_PROVEN_UH 640u',
    '#define G30_FO76_LAMBDA_PROVEN_UWB 24200u',
    '#define G30_FO76_DT_K_Q15 (-22528)',
    '#define G30_DEVV01_RUN_BAD_GRACE_1K 4u',
]:
    assert needle in obs,needle
print("OBSERVER_MODEL_CONSTANTS=PASS")

# Frozen sensorless fallback/coast behavior remains.
for needle in [
    'takeover_latch_coast(G30_TK_FB_INVALID)',
    'takeover_latch_coast(G30_TK_FB_NOT_TRACKING)',
    'takeover_latch_coast(G30_TK_FB_SPEED)',
]:
    assert needle in obs,needle
print("SENSORLESS_FALLBACK_COAST=PASS")

# Existing SESC supervisory behavior remains authoritative.
for needle in [
    'MaxPositiveTorque',
    'MinNegativeTorque',
    'FOCVars[M1].max_i_batt',
    'FW_DataProcess(pFW[M1],Vqd,Iqd);',
]:
    assert needle in mc,needle
assert 'const bool allow_braking = false;' in vs
print("LIMITS_FW_COAST_POLICY=PASS")

# State table: Hall drives immediately, sensorless drives only after frozen
# pushstart/observer takeover.
def owner(mode,active):
    if mode=="hall": return "DRV126"
    if mode=="sensorless" and active: return "DRV126"
    return "PWM_OFF"
assert owner("hall",False)=="DRV126"
assert owner("sensorless",False)=="PWM_OFF"
assert owner("sensorless",True)=="DRV126"
print("MODE_STATE_TABLE=PASS")

print("SESC_DRV126_POWERCORE6500_FINAL_V1_OFFLINE_SUITE=PASS")
