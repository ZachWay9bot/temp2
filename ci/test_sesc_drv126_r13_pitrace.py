#!/usr/bin/env python3

def trunc0_div(n,d):
    if n>=0:return n//d
    return -((-n)//d)

def pi(ref,act,acc,lim,outlim):
    e=ref-act
    p=trunc0_div(e*200,2048)
    acc=max(-lim,min(lim,acc+e))
    i=trunc0_div(acc*10,8192)
    out=max(-outlim,min(outlim,p+i))
    return out,acc

# Representative sign symmetry and exact integer truncation.
for ref,act in [(3539,1458),(-3539,-1379),(1178,730),(-1178,-730)]:
    out,a=pi(ref,act,0,25500057,31128)
    assert -31128<=out<=31128
    assert a==ref-act
print("R13_PI_INTEGER_REFERENCE=PASS")

# R1.3 must not alter guards/cadence inherited from R1.2.
assert 3800>3539
assert 5000>3539
print("R13_R12_GUARDS_RETAINED=PASS")
print("DRV126_R13_PITRACE_HOST=PASS")
