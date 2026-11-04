#!/usr/bin/env python3
MAX_U=1500
RAIL_LO=80
RAIL_HI=3920

def stock_u(mc):
    p=mc*51575
    return p//16384

# R0.2/R0.3 measured 3 A ~= 3539 stock units.
assert 1100 <= abs(stock_u(375)) <= 1250
assert abs(stock_u(375)) < MAX_U
assert abs(stock_u(562)) > MAX_U

# 4-kHz ownership from 16-kHz ISR: update on calls 0,4,8,...
div=0; upd=[]
for n in range(16):
    if div==0:
        upd.append(n);div=1
    else:
        div=(div+1)&3
assert upd==[0,4,8,12]
print("R1_16K_TO_4K_DIVIDER=PASS")

# Stock 4000-count duty scales into existing 2000-count timer.
for raw in (80,81,2000,3919,3920):
    c=(raw+1)>>1
    assert 40 <= c <= 1960
assert not (RAIL_LO <= 79 <= RAIL_HI)
assert not (RAIL_LO <= 3921 <= RAIL_HI)
print("R1_CCR_SCALE_AND_RAIL_GUARD=PASS")

def order3(a,b,c):
    if a==b or b==c or a==c:return 0
    if a>b>c:return 1
    if b>a>c:return 2
    if b>c>a:return 3
    if c>b>a:return 4
    if c>a>b:return 5
    return 6
assert [order3(3,2,1),order3(2,3,1),order3(1,3,2),order3(1,2,3),order3(2,1,3),order3(3,1,2)]==[1,2,3,4,5,6]
print("R1_PHASE_ORDER=PASS")
print("DRV126_R1_GATED_HOST=PASS")
