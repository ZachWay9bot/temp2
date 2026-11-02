#!/usr/bin/env python3
NO,SINGLE,DOUBLE,LONG=0,1,2,3
class SM:
    def __init__(self):
        self.pressed=0; self.pending=0; self.startup_armed=0
        self.pressed_at=0; self.released_at=0
    def step(self, now, down):
        if not self.startup_armed:
            if not down:
                self.startup_armed=1
                self.pressed=0; self.pending=0
            return NO
        if down and not self.pressed:
            self.pressed=1; self.pressed_at=now
            if self.pending==1 and now-self.released_at<=250:
                self.pending=2
        elif (not down) and self.pressed:
            self.pressed=0
            held=now-self.pressed_at
            if held>=2500:
                self.pending=0; return LONG
            if held>=30:
                if self.pending==2:
                    self.pending=0; return DOUBLE
                self.pending=1; self.released_at=now
            elif self.pending==2:
                self.pending=1
        if (not self.pressed) and self.pending==1 and now-self.released_at>250:
            self.pending=0; return SINGLE
        return NO

def run_segment(sm,t0,dur,down,dt=10):
    ev=[]; t=t0
    end=t0+dur
    while t<=end:
        e=sm.step(t,down)
        if e: ev.append((t,e))
        t+=dt
    return t,ev

# Normal G30 power-on: same button is held during boot, then released.
sm=SM(); t=0; events=[]
t,e=run_segment(sm,t,1800,True); events+=e
t,e=run_segment(sm,t,600,False); events+=e
assert events==[], events
assert sm.startup_armed==1

# First real short click must produce exactly one SINGLE.
t,e=run_segment(sm,t,150,True); events=e[:]
t,e=run_segment(sm,t,400,False); events+=e
assert [x[1] for x in events]==[SINGLE], events

# Second normal click also works.
t,e=run_segment(sm,t,120,True); events=e[:]
t,e=run_segment(sm,t,400,False); events+=e
assert [x[1] for x in events]==[SINGLE], events

# Double click: second press begins within 250 ms.
t,e=run_segment(sm,t,100,True); events=e[:]
t,e=run_segment(sm,t,120,False); events+=e
t,e=run_segment(sm,t,100,True); events+=e
t,e=run_segment(sm,t,300,False); events+=e
assert [x[1] for x in events]==[DOUBLE], events

# Long press after startup remains long press.
t,e=run_segment(sm,t,3000,True); events=e[:]
t,e=run_segment(sm,t,100,False); events+=e
assert LONG in [x[1] for x in events], events

# External-power boot with input already released must not synthesize a click.
sm2=SM(); events=[]
t,e=run_segment(sm2,0,500,False); events+=e
assert events==[] and sm2.startup_armed==1
print('R3I29 BUTTON BOOT-GATE HOST TEST: PASS')
