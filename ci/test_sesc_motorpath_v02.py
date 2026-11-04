#!/usr/bin/env python3

INT16_MAX=32767

def old_ic16(ia,ib):
    x=(-ia-ib) & 0xffff
    return x-0x10000 if x & 0x8000 else x

def v02_oc(ia,ib,threshold):
    ic=-int(ia)-int(ib)
    trip=(threshold>0 and
          (ia>threshold or ia<-threshold or
           ib>threshold or ib<-threshold or
           ic>threshold or ic<-threshold))
    ic_store=max(-INT16_MAX,min(INT16_MAX,ic))
    return trip,ic,ic_store

# Reproduce the exact class of hole V0.1 still had:
# Ia and Ib are individually below the ~60 A threshold, while true reconstructed
# Ic exceeds it. Narrowing Ic first wraps it back under threshold.
thr=22480
ia=22000
ib=22000
wrapped=old_ic16(ia,ib)
assert abs(ia)<thr and abs(ib)<thr and abs(wrapped)<thr
trip,ic,stored=v02_oc(ia,ib,thr)
assert ic==-44000
assert trip
assert stored==-INT16_MAX
print("OCP_IC_WRAP_HOLE_REPRODUCED=PASS")
print("OCP_IC_WIDE_COMPARE_TRIPS=PASS")
print("OCP_IC_LEGACY_FIELD_SATURATES=PASS")

# Normal balanced current remains unchanged in range.
trip,ic,stored=v02_oc(5000,-2500,thr)
assert not trip and ic==-2500 and stored==-2500
print("OCP_NORMAL_CURRENT_UNCHANGED=PASS")

# All individual phase directions are covered.
for ia,ib in [(23000,0),(-23000,0),(0,23000),(0,-23000),(22000,22000),(-22000,-22000)]:
    assert v02_oc(ia,ib,thr)[0]
print("OCP_ALL_PHASE_DIRECTIONS=PASS")
