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
