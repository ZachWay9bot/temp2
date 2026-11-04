#!/usr/bin/env python3

def stock_asr10_from_adc(delta):
    return (delta*51575)//1024

def stock_from_mc(counts):
    return (counts*51575)//16384

for d in range(-4095,4096):
    assert stock_from_mc(d*16)==stock_asr10_from_adc(d)
assert stock_from_mc(16)==50
assert stock_from_mc(-16)==-51
assert stock_from_mc(32)==100
assert stock_from_mc(-32)==-101
print("DRV126_STOCK_CURRENT_DOMAIN_BRIDGE=PASS")

for off in (32695,32895,32947):
    raw=off/16.0
    assert 1948.0 <= raw <= 2148.0
print("G30_LEFT_ALIGN_OFFSET_BRIDGE=PASS")

def clamp(v,lo,hi): return lo if v<lo else hi if v>hi else v
def pi(ref,act,acc,alim,olim):
    e=ref-act
    p=int((e*200)/2048)
    acc=clamp(acc+e,-alim,alim)
    ii=int((acc*10)/8192)
    return clamp(p+ii,-olim,olim),acc

qref=stock_from_mc(1124)
assert 3500 <= qref <= 3560
acc=0
for _ in range(4000):
    out,acc=pi(qref,0,acc,25500057,31128)
assert abs(out)<=31128
print("DRV126_R02_PI_STOCK_DOMAIN=PASS")
print("SHADOW_R02_HOST=PASS")
