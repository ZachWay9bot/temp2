from pathlib import Path
import hashlib, math, random, re

root=Path('SOURCE_KOXX3')
mc=(root/'common_files/src/mc_tasks.c').read_text()
vs=(root/'common_files/src/VescToSTM.c').read_text()
obs=(root/'common_files/src/g30_fo76_shadow.c').read_text()
obsh=(root/'common_files/src/g30_fo76_shadow.h').read_text()
it=(root/'common_files/src/stm32f10x_mc_it.c').read_text()
led=(root/'common_files/src/task_LED.c').read_text()
te=(root/'common_files/src/terminal.c').read_text()
de=(root/'common_files/src/defines.h').read_text()

assert 'SESC-DRV126-HYBRID-FINAL-V1' in de
print('HYBRID_BUILD_ID=PASS')

def dpp_to_erpm(dpp): return dpp*16000*60/65536.0
def dpp_to_kmh(dpp):
    erpm=dpp_to_erpm(dpp)
    mech_rpm=erpm/15.0
    return mech_rpm*math.pi*0.25*60/1000
entry=dpp_to_kmh(64)
ret=dpp_to_kmh(48)
nohall=dpp_to_kmh(40)
assert 2.90 < entry < 3.00
assert 2.15 < ret < 2.30
assert 1.80 < nohall < 1.90
print(f'HYBRID_SPEEDS entry={entry:.3f}kmh return={ret:.3f}kmh nohall_coast={nohall:.3f}kmh')

gates={
 'drv126_only_current_core': 'if(VescToSTM_g30_hall_selected()){' in mc and 'g30_drv126_final_hall_step' in mc,
 'observer_background_from_actual_pwm': 'g30_old_ca' in mc and 'g30_fo76_shadow_step(Iab.a,Iab.b,HALL_M1._Super.hElAngle' in mc,
 'auto_entry_64': 'G30_HYBRID_TAKEOVER_DPP' in mc and 'g30_fo76_request_takeover(1u);' in mc,
 'hysteresis_return_48': '#define G30_HYBRID_RETURN_DPP 48u' in obsh and 'observer_speed_dpp<=G30_HYBRID_RETURN_DPP' in obs,
 'return_blend': 'G30_TK_RETURN_BLEND=5' in obs and 'sensorless_external=0u;' in obs,
 'observer_commit': 'if(hybrid_mode)' in obs and 'sensorless_external=1u;' in obs,
 'hall_guard_only_before_takeover': '!g30_fo76_sensorless_active() &&' in mc,
 'hall_irq_isolated_after_takeover': 'VescToSTM_g30_hall_selected() && !g30_fo76_sensorless_active()' in it,
 'hybrid_stop_clears_observer_after_gates': 'if(VescToSTM_g30_hall_selected() && g30_fo76_sensorless_active())' in vs and 'g30_fo76_sensorless_clear();' in vs,
 'observer_speed_to_mc': '(VescToSTM_g30_sensorless_selected() || VescToSTM_g30_hall_selected())' in mc,
 'pure_sensorless_retained': 'VescToSTM_g30_sensorless_selected()' in vs and '#define R3I_MIN_DPP 64' in (root/'common_files/src/g30_r3i_pushstart.c').read_text(),
 'coast_no_regen': 'const bool allow_braking = false;' in vs,
 'diag_visible': 'HYBRID-SENSORLESS' in te and 'HYBRID-HALL' in te,
}
for k,v in gates.items():
    print(k, int(v))
assert all(gates.values()), gates
print('HYBRID_ARCHITECTURE_GATES=PASS')

for needle in [
 '#define G30_FO76_R_PROVEN_MOHM 583u',
 '#define G30_FO76_L_PROVEN_UH 640u',
 '#define G30_FO76_LAMBDA_PROVEN_UWB 24200u',
 '#define G30_FO76_DT_K_Q15 (-22528)',
 '#define G30_FO76_MIN_TRACK_DPP 40',
 '#define G30_DEVV01_RUN_BAD_GRACE_1K 4u',
]: assert needle in obs, needle
print('HYBRID_OBSERVER_PHYSICAL_MODEL_UNCHANGED=PASS')

for name,expected in [
 ('g30_r3i_pushstart.c','7e73fe8e08a28ce9c500e2fe31bc368d6ddbded3495349949cb85d54a4730c5e'),
 ('g30_r3i_pushstart.h','a660d0b1d4695492d8a356fccb65a0d0f28d751e589ad68a8ede06f8d72a6893'),
]:
    got=hashlib.sha256((root/'common_files/src'/name).read_bytes()).hexdigest()
    assert got==expected,(name,got)
print('HYBRID_PURE_SENSORLESS_PUSHSTART_UNCHANGED=PASS')

drv_needles=[
 'static int32_t g30_drv126_final_q_acc=0;',
 'counts*51575',
 '((ia+2*ib)*2365)>>12',
 '25500057,31128',
 '8500019,10376',
 'const int32_t per=4000,lim=3920',
 'pHdl->Sector=(uint8_t)(sec-1u);',
]
for needle in drv_needles:
    assert needle in mc,needle
print('HYBRID_DRV126_MATH_CORE_RETAINED=PASS')

HALL=0; ARMED=1; BLEND=2; OBS=3; FALL=4; RETURN=5
class Hybrid:
    def __init__(self):
        self.state=HALL; self.ext=False; self.req=False; self.off=0; self.coast=False
    def request(self,enable): self.req=bool(enable)
    def step(self,hall,pred,hspeed,ospeed,valid=True,tracking=True,hall_valid=True,hybrid=True):
        pred_err=((pred-hall+32768)&0xffff)-32768
        abs_err=abs(pred_err)
        if not self.req and not self.ext:
            self.state=HALL; return hall
        if self.state in (HALL,FALL) and self.req:
            self.state=ARMED
        if self.state==ARMED:
            if valid and tracking and hspeed<=-64 and abs_err<3641:
                self.off=((hall-pred+32768)&0xffff)-32768; self.state=BLEND
            else: return hall
        if self.state==BLEND:
            if not valid or not tracking or abs(hspeed)<48 or abs_err>=5461:
                self.state=FALL; self.req=False; return hall
            out=(pred+self.off)&0xffff
            if self.off>4:self.off-=4
            elif self.off<-4:self.off+=4
            else:
                self.off=0; self.state=OBS
                if hybrid:self.ext=True
            return out
        hall_return_ok=hybrid and hall_valid and hspeed<0 and abs_err<5461
        if self.state==RETURN:
            if not hall_return_ok:
                self.off=0; self.state=OBS
            else:
                out=(hall+self.off)&0xffff
                if self.off>4:self.off-=4
                elif self.off<-4:self.off+=4
                else:
                    self.off=0; out=hall; self.ext=False; self.req=False; self.state=HALL
                return out
        if hybrid and self.ext:
            if hall_return_ok and (ospeed<=48 or not valid or not tracking):
                self.off=pred_err; self.state=RETURN; return (hall+self.off)&0xffff
            if not valid or not tracking or ospeed<40:
                self.coast=True; self.state=FALL; self.req=False; return pred
        else:
            if not valid or not tracking or ospeed<64:
                self.coast=True; self.state=FALL; self.req=False; return pred
        self.state=OBS; return pred

h=Hybrid(); h.request(False)
for sp in [0,-10,-40,-63]: assert h.step(1000,1000,sp,abs(sp))==1000 and h.state==HALL
print('SCENARIO_LOW_SPEED_HALL=PASS')

h=Hybrid(); h.request(True)
for _ in range(500): h.step(1000,1000,80,80)
assert h.state==ARMED and not h.ext
print('SCENARIO_REVERSE_HALL_ONLY=PASS')

h=Hybrid(); h.request(True)
out=h.step(20000,19000,-64,64)
assert h.state==BLEND and out==20000
for _ in range(400): h.step(20000,19000,-70,70)
assert h.state==OBS and h.ext
print('SCENARIO_FWD_3KMH_ENTRY_BUMPLESS=PASS')

out=h.step(20000,19020,-49,49,True,True,True)
assert h.state==OBS and h.ext
out=h.step(20000,19020,-48,48,True,True,True)
assert h.state==RETURN and out==19020
for _ in range(400): h.step(20000,19020,-47,47,True,True,True)
assert h.state==HALL and not h.ext and not h.req
print('SCENARIO_64_48_HYSTERESIS_RETURN=PASS')

h=Hybrid(); h.req=True; h.ext=True; h.state=OBS
out=h.step(30000,29500,-90,90,False,True,True)
assert h.state==RETURN and not h.coast
print('SCENARIO_OBSERVER_BAD_GOOD_HALL_RETURN=PASS')

h=Hybrid(); h.req=True; h.ext=True; h.state=OBS
h.step(30000,29500,-90,90,False,True,False)
assert h.coast and h.state==FALL
print('SCENARIO_OBSERVER_BAD_NO_HALL_COAST=PASS')

h=Hybrid(); h.req=True; h.ext=True; h.state=OBS
for sp in [100,80,60,41]:
    h.step(0,20000,-sp,sp,True,True,False)
    assert h.state==OBS and not h.coast
h.step(0,20000,-39,39,True,True,False)
assert h.coast
print('SCENARIO_HALL_LOSS_SENSORLESS_CONTINUE_THEN_COAST=PASS')

h=Hybrid(); h.req=True; h.ext=True; h.state=RETURN; h.off=-1000
h.step(20000,19000,-47,47,True,True,False)
assert h.state==OBS and h.ext and not h.coast
print('SCENARIO_RETURN_ABORT_ON_HALL_LOSS=PASS')

for initial in [-5460,-3640,-1000,-5,0,5,1000,3640,5460]:
    off=initial
    last=off
    for _ in range(2000):
        if off>4:off-=4
        elif off<-4:off+=4
        else:off=0
        assert abs(off-last)<=4
        last=off
        if off==0:break
    assert off==0
print('SCENARIO_BLEND_STEP_BOUND=PASS')

for needle in ['MaxPositiveTorque','MinNegativeTorque','FOCVars[M1].max_i_batt','FW_DataProcess(pFW[M1],Vqd,Iqd);']:
    assert needle in mc
print('HYBRID_LIMITS_AND_FW_RETAINED=PASS')

print('DRV126_HYBRID_FINAL_V1_OFFLINE_SUITE=PASS')
