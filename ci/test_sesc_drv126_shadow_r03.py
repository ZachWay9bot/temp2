#!/usr/bin/env python3
def asr(v,s):
    if v>=0:return v>>s
    return -(((-v)+((1<<s)-1))>>s)

def inv(q,d,co,si):
    return asr(co*q+si*d,15),asr(si*q-co*d,15)

def svm(alpha,beta):
    per=4000;lim=3920
    t=asr(alpha*1774,10)
    x=asr(beta+t,1);y=asr(beta-t,1)
    if x<0:
        if y<0:sec=5
        elif beta<=0:sec=4
        else:sec=3
    else:
        if y>=0:sec=2
        elif beta<=0:sec=6
        else:sec=1
    X=asr(x*per,15);Y=asr(y*per,15);B=asr(beta*per,15)
    if sec==1:
        u,v,den=B,-Y,B-Y
        if den>lim:u,v=(B*lim)//den,((-Y)*lim)//den
        z=asr(per-v-u,1);c3=z;c2=z+u;c1=c2+v
    elif sec==2:
        u,v,den=X,Y,Y+X
        if den>lim:v,u=(Y*lim)//den,(X*lim)//den
        z=asr(per-u-v,1);c3=z;c1=z+u;c2=c1+v
    elif sec==3:
        u,v,den=B,-X,B-X
        if den>lim:v,u=((-X)*lim)//den,(B*lim)//den
        z=asr(per-u-v,1);c1=z;c3=z+v;c2=c3+u
    elif sec==4:
        u,v,den=Y,-B,Y-B
        if den>lim:u,v=(Y*lim)//den,((-B)*lim)//den
        z=asr(per-u-v,1);c1=z;c2=z+u;c3=c2+v
    elif sec==5:
        u,v,den=-Y,-X,(-Y)+(-X)
        if den>lim:u,v=((-Y)*lim)//den,((-X)*lim)//den
        z=asr(per-v-u,1);c2=z;c1=z+u;c3=c1+v
    else:
        u,v,den=X,-B,X-B
        if den>lim:v,u=((-B)*lim)//den,(X*lim)//den
        z=asr(per-v-u,1);c2=z;c3=z+v;c1=c3+u
    return sec,(max(0,min(4000,c1)),max(0,min(4000,c2)),max(0,min(4000,c3)))

# Exact inverse-Park axis identities at cardinal trig points.
assert inv(1000,200,32766,0)==(999,-200)
assert inv(1000,200,0,32766)==(199,999)
print("DRV126_INV_PARK_CARDINAL=PASS")

# Sector and duty-order identities reconstructed from the TBB cases.
vectors=[(4000,12000,1),(-4000,12000,2),(-12000,4000,3),(-12000,-4000,4),(4000,-12000,5),(12000,-4000,6)]
orders={1:(0,1,2),2:(1,0,2),3:(1,2,0),4:(2,1,0),5:(2,0,1),6:(0,2,1)}
for a,b,exp in vectors:
    sec,ccr=svm(a,b)
    assert sec==exp,(a,b,sec,exp)
    assert len(set(ccr))==3,(sec,ccr)
    idx=tuple(sorted(range(3),key=lambda i:-ccr[i]))
    assert idx==orders[sec],(sec,ccr,idx)
print("DRV126_SVPWM_SECTOR_ORDER=PASS")

# Exact sector-boundary vectors are allowed to have equal CCRs.
for a,b in [(0,12000),(12000,0),(-12000,0),(0,-12000)]:
    sec,ccr=svm(a,b)
    assert 1<=sec<=6 and max(ccr)-min(ccr)<=3920
print("DRV126_SVPWM_BOUNDARY_TIES=PASS")

# Dense range/overmod gate. The stock active span is never above 3920.
for a in range(-32768,32768,1024):
  for b in range(-32768,32768,1024):
    sec,c=svm(a,b)
    assert 1<=sec<=6
    assert all(0<=x<=4000 for x in c)
    assert max(c)-min(c)<=3920
print("DRV126_SVPWM_RANGE_OVERMOD=PASS")

# Zero vector is centered.
sec,c=svm(0,0)
assert c==(2000,2000,2000)
print("DRV126_SVPWM_ZERO_CENTER=PASS")
print("SHADOW_R03_HOST=PASS")
