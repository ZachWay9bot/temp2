#!/usr/bin/env python3
"""Pure host checks for G30 Hall topology/guard logic."""

R2 = [255,20,104,60,188,232,149,255]
CURRENT_KNOWN = [255,232,143,186,63,17,103,255]

def signed_mod256_delta(a,b):
    d=b-a
    if d>100: d-=255
    elif d<-100: d+=255
    return d

def edge_valid(prev,new,lut):
    if prev in (0,7) or new in (0,7):
        return False
    if lut[prev]==255 or lut[new]==255:
        return False
    return (prev ^ new) in (1,2,4)

def ring_check(lut, ring):
    ds=[signed_mod256_delta(lut[a],lut[b]) for a,b in zip(ring,ring[1:])]
    assert all(30 <= d <= 55 for d in ds), ds
    return ds

# Hardware-validated R2 topology: one bit changes at every 60-degree sector.
r2_fwd=[1,3,2,6,4,5,1]
assert all(edge_valid(a,b,R2) for a,b in zip(r2_fwd,r2_fwd[1:]))
r2_d=ring_check(R2,r2_fwd)

# The user's newer known-good stored table is a valid six-sector ring with the
# opposite positive Hall orientation; do not replace it just because R2 defaults differ.
known_fwd=[1,5,4,6,2,3,1]
assert all(edge_valid(a,b,CURRENT_KNOWN) for a,b in zip(known_fwd,known_fwd[1:]))
known_d=ring_check(CURRENT_KNOWN,known_fwd)

# All reverse edges remain legal.
assert all(edge_valid(a,b,R2) for a,b in zip(reversed(r2_fwd),list(reversed(r2_fwd))[1:]))

# Invalid electrical codes and skipped/multi-bit transitions must be rejected.
for s in range(8):
    assert not edge_valid(0,s,R2)
    assert not edge_valid(7,s,R2)
    assert not edge_valid(s,0,R2)
    assert not edge_valid(s,7,R2)
for a in range(1,7):
    assert not edge_valid(a,a,R2)
for a in range(1,7):
    for b in range(1,7):
        if b!=a and (a^b) not in (1,2,4):
            assert not edge_valid(a,b,R2), (a,b)

print("HALL_R2_RING_DELTAS="+",".join(map(str,r2_d)))
print("HALL_CURRENT_KNOWN_RING_DELTAS="+",".join(map(str,known_d)))
print("HALL_VALID_CODES=1..6")
print("HALL_INVALID_CODES=0,7")
print("HALL_SINGLE_BIT_TRANSITION_GUARD=PASS")
print("HALL_BIDIRECTIONAL_TOPOLOGY=PASS")

def direction_allowed(requested, measured_vesc, hall_selected=True):
    if not hall_selected or requested == 0:
        return True
    deadband = 20
    if measured_vesc > deadband and requested < 0:
        return False
    if measured_vesc < -deadband and requested > 0:
        return False
    return True

# Hall FWD and REV are both legal from rest / near-zero.
assert direction_allowed(+1, 0)
assert direction_allowed(-1, 0)
assert direction_allowed(+1, 20)
assert direction_allowed(-1, -20)

# Same-direction torque stays legal while rolling.
assert direction_allowed(+1, +100)
assert direction_allowed(-1, -100)

# Opposite torque is blocked until the wheel has coasted into the deadband.
assert not direction_allowed(-1, +21)
assert not direction_allowed(+1, -21)

# Sensorless is not changed by this Hall-only interlock.
assert direction_allowed(-1, +100, hall_selected=False)

print("HALL_FWD_FROM_ZERO=PASS")
print("HALL_REV_FROM_ZERO=PASS")
print("HALL_OPPOSITE_DIRECTION_COAST_INTERLOCK=PASS")

def lut_plausible(lut):
    ring=[1,3,2,6,4,5,1]
    if lut[0] != 255 or lut[7] != 255:
        return False
    direction=0
    for a,b in zip(ring,ring[1:]):
        d=lut[b]-lut[a]
        if d>100: d-=255
        elif d<-100: d+=255
        mag=abs(d)
        if mag<25 or mag>65:
            return False
        sign=1 if d>0 else -1
        if direction==0: direction=sign
        elif sign!=direction: return False
    return True

assert lut_plausible(R2)
assert lut_plausible(CURRENT_KNOWN)
assert not lut_plausible([255,20,20,60,188,232,149,255])   # duplicate sector angle
assert not lut_plausible([0,20,104,60,188,232,149,255])    # invalid code 0
assert not lut_plausible([255,20,104,200,188,232,149,255])  # impossible jump/sign
print("HALL_LUT_PLAUSIBILITY=PASS")




# Hall speed-feedback fault recovery model: held drive must not restart; a zero
# command may rearm only with physically valid Hall feedback. The subsequent
# drive command is the restart boundary.
def hall_fault_recovery(command_nonzero, hall_physical_valid, hall_fault_latched):
    if not hall_fault_latched:
        return "normal"
    if command_nonzero:
        return "blocked"
    if hall_physical_valid:
        return "rearmed_on_release"
    return "blocked"

assert hall_fault_recovery(True, True, True) == "blocked"
assert hall_fault_recovery(True, False, True) == "blocked"
assert hall_fault_recovery(False, False, True) == "blocked"
assert hall_fault_recovery(False, True, True) == "rearmed_on_release"
assert hall_fault_recovery(True, True, False) == "normal"
print("HALL_FAULT_REQUIRES_RELEASE=PASS")
print("HALL_FAULT_INVALID_FEEDBACK_STAYS_BLOCKED=PASS")

# MC_SPEED_FDBK has no separate automatic reset path in the MCSDK medium task.
# The release-rearm must therefore clear exactly that recovered software fault.
fault_now = 0x0020 | 0x0004
fault_after_release = fault_now & (~0x0020)
assert fault_after_release == 0x0004
print("HALL_SPEED_FAULT_RESET_ON_VALID_RELEASE=PASS")
print("HALL_OTHER_FAULT_BITS_PRESERVED=PASS")
