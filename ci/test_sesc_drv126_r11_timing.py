#!/usr/bin/env python3

def floor_shift(v,s):
    if v>=0:return v>>s
    return -(((-v)+((1<<s)-1))>>s)

def stock_u(mc):
    p=mc*51575
    return floor_shift(p,14)

# Exact equivalence to prior R0.2/R0.3 bridge for all int16 endpoints/sample grid.
def old_stock_u(mc):
    p=mc*51575
    if p>=0:return p//16384
    return -(((-p)+16383)//16384)

for x in list(range(-32768,32768,31))+[-32768,-32767,-1,0,1,32766,32767]:
    assert stock_u(x)==old_stock_u(x)
print("R11_STOCK_U_32BIT_EQUIVALENCE=PASS")

# Generic floor-ASR replacement matches integer floor division in all transform ranges.
for s in (1,10,12,15):
    for v in range(-1000000,1000001,9973):
        assert floor_shift(v,s)==v//(1<<s)
print("R11_ASR32_EQUIVALENCE=PASS")

# Every 16-kHz ISR must perform the ADC/sample-point commit; control state updates 4 kHz.
div=0; control=[]; commit=[]
for n in range(16):
    if div:
        div=(div+1)&3
        commit.append(n)
    else:
        div=1
        control.append(n);commit.append(n)
assert control==[0,4,8,12]
assert commit==list(range(16))
print("R11_4K_CONTROL_16K_COMMIT=PASS")
print("DRV126_R11_TIMING_HOST=PASS")
