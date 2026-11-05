#!/usr/bin/env python3

def stock_u(mc):
    p=mc*51575
    if p>=0:return p>>14
    return -(((-p)+16383)>>14)

# Current-domain anchors from the already validated bridge:
# ~375 MCSDK counts/A -> ~1179 DRV126 internal units/A.
u1=abs(stock_u(375))
u2=abs(stock_u(750))
u3=abs(stock_u(1125))
print("U_1A",u1,"U_2A",u2,"U_3A",u3)
assert 1100 <= u1 <= 1250
assert 2250 <= u2 <= 2450
assert 3450 <= u3 <= 3650
assert u3 < 3800
assert abs(stock_u(1250)) > 3800
print("R12_QREF_3A_GUARD=PASS")

# Phase guard ~4.2A equivalent: enough transient headroom, still far below 60A OCP.
assert abs(stock_u(1500)) < 5000
assert abs(stock_u(1700)) > 5000
print("R12_PHASE_GUARD=PASS")

print("DRV126_R12_LOADSYM_HOST=PASS")
