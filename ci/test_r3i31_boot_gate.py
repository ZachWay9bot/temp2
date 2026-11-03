#!/usr/bin/env python3
NO,SINGLE,DOUBLE,LONG=0,1,2,3
class SM:
    def __init__(self):
        self.pressed=0; self.pending=0; self.startup_armed=0
        self.pressed_at=0; self.released_at=0
        self.single=0
    def step(self,now,down):
        if not self.startup_armed:
            if not down:
                self.startup_armed=1; self.pressed=0; self.pending=0
            return NO
        if down and not self.pressed:
            self.pressed=1; self.pressed_at=now
            if self.pending==1 and now-self.released_at<=250: self.pending=2
        elif (not down) and self.pressed:
            self.pressed=0; held=now-self.pressed_at
            if held>=2500:
                self.pending=0; return LONG
            if held>=30:
                if self.pending==2:
                    self.pending=0; return DOUBLE
                self.pending=1; self.released_at=now
            elif self.pending==2:
                self.pending=1
        if (not self.pressed) and self.pending==1 and now-self.released_at>250:
            self.pending=0; self.single+=1; return SINGLE
        return NO

def seg(sm,t,dur,down,step=10):
    ev=[]
    end=t+dur
    while t<=end:
        e=sm.step(t,down)
        if e: ev.append((t,e))
        t+=step
    return t,ev

# Physical-button power-on: held through boot, release must NOT become SINGLE.
sm=SM(); t=0; ev=[]
t,e=seg(sm,t,1500,True); ev+=e
t,e=seg(sm,t,500,False); ev+=e
assert ev==[] and sm.startup_armed==1 and sm.single==0, (ev,sm.__dict__)

# First actual click works once.
t,e=seg(sm,t,180,True); ev=e[:]
t,e=seg(sm,t,400,False); ev+=e
assert [x[1] for x in ev]==[SINGLE] and sm.single==1, (ev,sm.__dict__)

# External 5-V boot, button already released: no synthesized click.
sm2=SM(); t=0; ev=[]
t,e=seg(sm2,t,600,False); ev+=e
assert ev==[] and sm2.startup_armed==1 and sm2.single==0, (ev,sm2.__dict__)
print('R3I31 BOOT-GATE HOST TEST: PASS')
