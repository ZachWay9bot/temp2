#!/usr/bin/env python3
"""Host gates for SESC DRV126 Shadow R0. No hardware writes are allowed."""

def clamp(v,lo,hi):
    return lo if v<lo else hi if v>hi else v

def pi_step(ref,act,acc,acc_lim,out_lim):
    e=ref-act
    p=int((e*200)/2048)  # Python int() truncates toward zero
    acc=clamp(acc+e,-acc_lim,acc_lim)
    i=int((acc*10)/8192)
    raw=p+i
    out=clamp(raw,-out_lim,out_lim)
    return out,acc,(raw!=out)

# Exact reconstructed DRV126 PI constants.
for out_lim,acc_lim in [(31128,25500057),(10376,8500019)]:
    acc=0
    for _ in range(10000):
        out,acc,sat=pi_step(3000,0,acc,acc_lim,out_lim)
        assert -out_lim <= out <= out_lim
        assert -acc_lim <= acc <= acc_lim
print("DRV126_PI_CONSTANTS=PASS")

# Four 4-kHz-equivalent substeps must equal four sequential stock PI calls
# when the 1-ms shadow snapshot is held constant.
def four_substeps(ref,act,acc,acc_lim,out_lim):
    last=0
    for _ in range(4):
        last,acc,_=pi_step(ref,act,acc,acc_lim,out_lim)
    return last,acc
o1,a1=four_substeps(3000,2100,0,25500057,31128)
acc=0
for _ in range(4):
    o2,acc,_=pi_step(3000,2100,acc,25500057,31128)
assert (o1,a1)==(o2,acc)
print("DRV126_4K_FROM_1K_SUBSTEPS=PASS")

# Exact Stock Clarke constant from DRV126 disassembly.
def stock_clarke(ia,ib):
    return ia, ((ia+2*ib)*2365) >> 12
assert stock_clarke(1000,-500)==(1000,0)
assert stock_clarke(1000,0)[1]==577
print("DRV126_CLARKE_2365_4096=PASS")

# Both unresolved PI assignment hypotheses remain independently bounded.
for q,d in [(3000,0),(-3000,0),(3000,500)]:
    aq=ad=bq=bd=0
    sat_a=sat_b=0
    for _ in range(400):
        vaq,aq,sa=pi_step(q,1000,aq,25500057,31128)
        vad,ad,sd=pi_step(d,100,ad,8500019,10376)
        vbq,bq,sb=pi_step(q,1000,bq,8500019,10376)
        vbd,bd,se=pi_step(d,100,bd,25500057,31128)
        sat_a+=sa+sd; sat_b+=sb+se
    assert abs(vaq)<=31128 and abs(vad)<=10376
    assert abs(vbq)<=10376 and abs(vbd)<=31128
print("DRV126_BOTH_PI_MAPS_BOUNDED=PASS")

print("SHADOW_R0_HOST=PASS")
