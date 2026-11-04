#!/usr/bin/env python3
import math

CURRENT_FACTOR_A=(32767.0*0.002*9.4336)/(3.3/2.0)
INT16_MAX=32767
SP_KIDIV=256

def oc_counts(abs_a):
    raw=abs_a*CURRENT_FACTOR_A
    return int(min(max(raw,0.0),float(INT16_MAX)))

# Current production setting remains exact enough and below saturation.
c60=oc_counts(60.0)
assert 22000 < c60 < 23000
print(f"OCP_60A_COUNTS={c60}")

# Reproduce the configuration hole: 100 A is a legal VESC/HW limit but cannot
# be represented in the legacy signed int16 threshold. V0.3 must saturate.
raw100=int(100.0*CURRENT_FACTOR_A)
assert raw100 > INT16_MAX
assert oc_counts(100.0)==INT16_MAX
print(f"OCP_100A_RAW_COUNTS={raw100}")
print("OCP_THRESHOLD_INT16_SATURATION=PASS")

# Boundary is about 87.45 A.
boundary=INT16_MAX/CURRENT_FACTOR_A
assert 87.0 < boundary < 88.0
print(f"OCP_MAX_REPRESENTABLE_A={boundary:.4f}")

def torque_limits(q, allow_braking):
    if q >= 0:
        wi_hi=q*SP_KIDIV
        wi_lo=-q*SP_KIDIV if allow_braking else 0
        ho_hi=q
        ho_lo=-q if allow_braking else 0
    else:
        wi_hi=-q*SP_KIDIV if allow_braking else 0
        wi_lo=q*SP_KIDIV
        ho_hi=-q if allow_braking else 0
        ho_lo=q
    return wi_lo,wi_hi,ho_lo,ho_hi

# Output limits are torque units, integral limits are Ki-divisor scaled.
for q in (11240,-11240):
    wi_lo,wi_hi,ho_lo,ho_hi=torque_limits(q,True)
    assert -INT16_MAX <= ho_lo <= INT16_MAX
    assert -INT16_MAX <= ho_hi <= INT16_MAX
    assert max(abs(wi_lo),abs(wi_hi)) == abs(q)*SP_KIDIV
    assert max(abs(ho_lo),abs(ho_hi)) == abs(q)
print("TORQUE_OUTPUT_LIMIT_SCALING=PASS")

# G30 explicitly ignores a stale allow-braking bit: opposite torque remains 0.
for q in (11240,-11240):
    wi_lo,wi_hi,ho_lo,ho_hi=torque_limits(q,False)
    if q>0:
        assert wi_lo==0 and ho_lo==0
    else:
        assert wi_hi==0 and ho_hi==0
print("G30_TORQUE_NO_REGEN_LIMITS=PASS")
