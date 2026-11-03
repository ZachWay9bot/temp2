#!/usr/bin/env python3

class SM:
    def __init__(self):
        self.pressed=0
        self.pending=0
        self.light_previewed=0
        self.pressed_at=0
        self.released_at=0
        self.light=0

    def step(self, down, now):
        if down and not self.pressed:
            self.pressed=1
            self.pressed_at=now
            if self.pending==1 and now-self.released_at <= 250:
                self.pending=2
                if self.light_previewed:
                    self.light ^= 1
                    self.light_previewed=0
        elif (not down) and self.pressed:
            self.pressed=0
            held=now-self.pressed_at
            if held >= 2500:
                self.pending=0
                self.light_previewed=0
                return "LONG"
            if held >= 30:
                if self.pending==2:
                    self.pending=0
                    return "DOUBLE"
                self.light ^= 1
                self.light_previewed=1
                self.pending=1
                self.released_at=now
            elif self.pending==2:
                self.pending=1
                if not self.light_previewed:
                    self.light ^= 1
                    self.light_previewed=1
                self.released_at=now
        if not self.pressed and self.pending==1 and now-self.released_at > 250:
            self.pending=0
            self.light_previewed=0
            return "SINGLE"
        return "NO"

def single(sm,t0):
    assert sm.step(1,t0)=="NO"
    assert sm.step(0,t0+100)=="NO"
    immediate=sm.light
    assert sm.step(0,t0+351)=="SINGLE"
    return immediate,sm.light

sm=SM()
assert single(sm,100)==(1,1)
assert single(sm,1000)==(0,0)
print("PASS single immediate ON then OFF")

sm=SM()
assert sm.step(1,100)=="NO"
assert sm.step(0,180)=="NO" and sm.light==1
assert sm.step(1,300)=="NO" and sm.light==0
assert sm.step(0,380)=="DOUBLE" and sm.light==0
print("PASS double cancels provisional light toggle")

sm=SM()
assert sm.step(1,100)=="NO"
assert sm.step(0,180)=="NO" and sm.light==1
assert sm.step(1,250)=="NO" and sm.light==0
assert sm.step(0,260)=="NO" and sm.light==1
assert sm.step(0,511)=="SINGLE" and sm.light==1
print("PASS bounced second press restores first click")

sm=SM()
assert sm.step(1,100)=="NO"
assert sm.step(0,2700)=="LONG" and sm.light==0
print("PASS long press leaves light unchanged")

print("R3I35 HOST STATE TEST: PASS")
