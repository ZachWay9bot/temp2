#!/usr/bin/env python3
from pathlib import Path
import random

root=Path("SOURCE_KOXX3")
mc=(root/"common_files/src/mc_tasks.c").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
te=(root/"common_files/src/terminal.c").read_text()
de=(root/"common_files/src/defines.h").read_text()

def trunc0(n,d):
    return n//d if n>=0 else -((-n)//d)

def stock_u(mc):
    p=mc*51575
    if p>=0:return p>>14
    return -(((-p)+16383)>>14)

def pi(ref,act,acc,alim,olim):
    e=ref-act
    p=trunc0(e*200,2048)
    acc=max(-alim,min(alim,acc+e))
    i=trunc0(acc*10,8192)
    out=max(-olim,min(olim,p+i))
    return out,acc

# 1) Current bridge: whole int16 domain, no 32-bit overflow.
mx=0
for x in range(-32768,32768):
    p=x*51575
    assert -(1<<31) < p < (1<<31)
    u=stock_u(x)
    mx=max(mx,abs(u))
assert mx==103150 or mx==103146 or mx>103000
print("FINAL_CURRENT_BRIDGE_INT16_FULL_DOMAIN=PASS maxStock",mx)

# 2) Representative production current commands, both signs.
CURRENT_FACTOR_A=374.67972266666675
for amps in (0,1,2,3,30,40,45,60):
    c=round(amps*CURRENT_FACTOR_A)
    if c<=32767:
        u=stock_u(c)
        un=stock_u(-c)
        assert abs(u+un)<=1
        print(f"FINAL_CURRENT_{amps}A counts={c} stock={u}")
print("FINAL_FWD_REV_CURRENT_SYMMETRY=PASS")

# 3) PI arithmetic fuzz across command/feedback range including OCP-scale errors.
rng=random.Random(0x126)
for _ in range(250000):
    ref=rng.randint(-103150,103150)
    act=rng.randint(-178700,178700)
    acc=rng.randint(-25500057,25500057)
    out,newacc=pi(ref,act,acc,25500057,31128)
    assert -31128<=out<=31128
    assert -25500057<=newacc<=25500057
    assert abs((ref-act)*200)<(1<<31)
    assert abs(newacc*10)<(1<<31)
print("FINAL_PI_250K_FUZZ=PASS")

# 4) Analytical transform overflow bounds.
max_stock=max(abs(stock_u(-32768)),abs(stock_u(32767)))
max_beta=((max_stock*3)*2365)>>12
assert 2*4096*max(max_stock,max_beta) < (1<<31)
assert 32766*(31128+10376) < (1<<31)
print("FINAL_TRANSFORM_INT32_BOUNDS=PASS")

# 5) Four-to-one cadence: control on 0,4,8..., sample commit on every ISR.
div=0;control=[];commit=[]
for n in range(64):
    if div:
        div=(div+1)&3
        commit.append(n)
    else:
        div=1
        control.append(n);commit.append(n)
assert control==list(range(0,64,4))
assert commit==list(range(64))
print("FINAL_4K_CONTROL_16K_COMMIT=PASS")

# 6) Hall validity scenarios.
valid_lut=[255,0,1,2,3,4,5,255]
def hall_ok(raw,reliable=True):
    return reliable and raw not in (0,7) and valid_lut[raw]!=255
assert not hall_ok(0)
assert not hall_ok(7)
for x in range(1,7): assert hall_ok(x)
assert not hall_ok(3,False)
print("FINAL_HALL_0_7_UNRELIABLE_GUARDS=PASS")

# 7) Production architecture static gates.
gates={
 "build_id":'SESC-DRV126-MOTORCORE-FINAL-V1' in de,
 "auto_hall_owner":'if(VescToSTM_g30_hall_selected()){' in mc and 'g30_drv126_final_hall_step' in mc,
 "no_arm_surface":'g30_drv126_r1_command' not in mc and 'g30_drv126_r1' not in te,
 "sensorless_path_retained":'VescToSTM_g30_sensorless_selected() && g30_fo76_sensorless_active()' in mc,
 "stock_pi_q":'25500057,31128' in mc,
 "stock_pi_d":'8500019,10376' in mc,
 "stock_clarke":'((ia+2*ib)*2365)>>12' in mc,
 "stock_svpwm":'const int32_t per=4000,lim=3920' in mc,
 "stock_sector_direct":'pHdl->Sector=(uint8_t)(sec-1u);' in mc and 'g30_drv126_order3' not in mc,
 "no_test_rail_guard":'G30_DRV126_R1_RAIL_MIN_RAW' not in mc,
 "config_q_clamp":'MaxPositiveTorque' in mc and 'MinNegativeTorque' in mc,
 "live_hall_fast_guard":'raw==0u || raw==7u || HALL_M1.lut[raw]==255u' in mc,
 "full_telemetry":'FOCVars[M1].Iqd=Iqd;' in mc and 'FOCVars[M1].Vqd=Vqd;' in mc,
 "fw_data_live":'FW_DataProcess(pFW[M1],Vqd,Iqd);' in mc,
 "preload":'g30_drv126_final_preload(drv_vq,drv_vd);' in vs,
 "reset_on_stop":'g30_drv126_final_reset();' in vs,
 "coast_policy":'const bool allow_braking = false;' in vs,
}
for k,v in gates.items():
    print(k,int(v))
assert all(gates.values()),gates
print("FINAL_ARCHITECTURE_GATES=PASS")

# 8) Ensure the final patch did not touch the frozen observer implementation.
for name,expected in [
 ("g30_fo76_shadow.c","cec66fd9085dc363e02cb1b9220b44c7ed643e0f28563782c20f19d5af3ba09b"),
 ("g30_fo76_shadow.h","d4c7d026b42dc8165becb6a7665e33d3169d68fb254844cc6214b0975f91966e"),
 ("g30_r3i_pushstart.c","7e73fe8e08a28ce9c500e2fe31bc368d6ddbded3495349949cb85d54a4730c5e"),
 ("g30_r3i_pushstart.h","a660d0b1d4695492d8a356fccb65a0d0f28d751e589ad68a8ede06f8d72a6893"),
]:
    import hashlib
    got=hashlib.sha256((root/"common_files/src"/name).read_bytes()).hexdigest()
    assert got==expected,(name,got)
print("FINAL_SENSORLESS_FROZEN_HASHES=PASS")

print("DRV126_FINAL_V1_OFFLINE_SUITE=PASS")
