#!/usr/bin/env python3
import argparse, re, struct, sys, time
from datetime import datetime

COMM_SET_RPM=8
COMM_TERMINAL_CMD=20
COMM_PRINT=21

def crc16(data:bytes)->int:
    crc=0
    for b in data:
        x=((crc>>8)&0xff)^b
        x^=x>>4
        crc=((crc<<8)^(x<<12)^(x<<5)^x)&0xffff
    return crc

def frame(payload:bytes)->bytes:
    n=len(payload)
    head=bytes((2,n)) if n<=255 else bytes((3,(n>>8)&0xff,n&0xff))
    c=crc16(payload)
    return head+payload+bytes((c>>8,c&0xff,3))

class Parser:
    def __init__(self): self.buf=bytearray()
    def feed(self,data):
        self.buf.extend(data); out=[]
        while True:
            if not self.buf: break
            try: i=next(i for i,b in enumerate(self.buf) if b in (2,3))
            except StopIteration: self.buf.clear(); break
            if i: del self.buf[:i]
            if len(self.buf)<2: break
            if self.buf[0]==2: n=self.buf[1]; h=2
            else:
                if len(self.buf)<3: break
                n=(self.buf[1]<<8)|self.buf[2]; h=3
            total=h+n+3
            if len(self.buf)<total: break
            pkt=bytes(self.buf[:total])
            if pkt[-1]!=3: del self.buf[0]; continue
            payload=pkt[h:h+n]; rx=(pkt[h+n]<<8)|pkt[h+n+1]
            if crc16(payload)!=rx: del self.buf[0]; continue
            del self.buf[:total]; out.append(payload)
        return out

class Link:
    def __init__(self,ser,fp):
        self.ser=ser; self.p=Parser(); self.fp=fp; self.current_rpm=0; self.last_rpm_tx=0.0
    def log(self,s):
        ts=datetime.now().strftime('%H:%M:%S.%f')[:-3]
        line=f'[{ts}] {s}'; print(line,flush=True); self.fp.write(line+'\n'); self.fp.flush()
    def send(self,payload): self.ser.write(frame(payload)); self.ser.flush()
    def set_rpm(self,rpm):
        self.current_rpm=int(rpm)
        self.send(bytes((COMM_SET_RPM,))+struct.pack('>i',self.current_rpm))
        self.last_rpm_tx=time.monotonic()
    def terminal(self,cmd): self.log('> '+cmd); self.send(bytes((COMM_TERMINAL_CMD,))+cmd.encode('ascii'))
    def poll(self,duration=.15,keep_rpm=False):
        end=time.monotonic()+duration; got=[]
        while time.monotonic()<end:
            if keep_rpm and self.current_rpm and time.monotonic()-self.last_rpm_tx>.10:
                self.set_rpm(self.current_rpm)
            n=self.ser.in_waiting
            if n:
                for payload in self.p.feed(self.ser.read(n)):
                    if payload and payload[0]==COMM_PRINT:
                        txt=payload[1:].decode('utf-8',errors='replace').replace('\r','')
                        for line in txt.split('\n'):
                            if line: self.log(line); got.append(line)
            else: time.sleep(.01)
        return got
    def query(self,cmd,wait=.4,keep_rpm=False):
        self.terminal(cmd); return self.poll(wait,keep_rpm)

def val(lines,pat,cast=int,default=None):
    rx=re.compile(pat)
    for line in reversed(lines):
        m=rx.search(line)
        if m:
            try: return cast(m.group(1))
            except Exception: pass
    return default

def status(link,keep=False):
    lines=link.query('g30_pushstart status',.30,keep)
    return {
        'lines':lines,
        'mode':val(lines,r'R3I mode=(\d+)',int,-1),
        'cal':val(lines,r'R3I mode=\d+ cal=(\d+)',int,-1),
        'started':val(lines,r'started=(\d+)',int,-1),
        'starts':val(lines,r'starts=(\d+)',int,-1),
        'frames':val(lines,r'frames=(\d+)',int,-1),
        'edges':val(lines,r'edges=(\d+)',int,-1),
        'span':val(lines,r'span=(\d+)',int,-1),
        'dpp':val(lines,r'dpp=(-?\d+)',int,None),
        'erpm':val(lines,r'erpm=(-?\d+)',int,None),
        'offset':val(lines,r'offset=(-?\d+)',int,None),
        'mcstate':val(lines,r'mcstate=(\d+)',int,-1),
        'pwm_off':val(lines,r'pwm_off=(\d+)',int,-1),
        'start_pending':val(lines,r'start_pending=(\d+)',int,-1),
        'adc_ready':val(lines,r'adc_ready=(\d+)',int,-1),
        'ha':val(lines,r'handles=(\d+),',int,-1),
        'hb':val(lines,r'handles=\d+,(\d+),',int,-1),
        'hc':val(lines,r'handles=\d+,\d+,(\d+)',int,-1),
    }

def wait_for_true_coast(link,phase,timeout=4.0):
    deadline=time.monotonic()+timeout
    last=None
    while time.monotonic()<deadline:
        last=status(link)
        link.log(f'COAST {phase}: mode={last["mode"]} mcstate={last["mcstate"]} pwm_off={last["pwm_off"]} adc_ready={last["adc_ready"]} handles={last["ha"]},{last["hb"]},{last["hc"]} frames={last["frames"]}')
        if last['mode']==1 and last['mcstate']==6 and last['pwm_off']==1 and last['adc_ready']==1 and last['frames']>=3:
            return last
        time.sleep(.15)
    return last

def control_diag(link,keep=False):
    lines=[]
    lines += link.query('g30_takeover status',.16,keep)
    lines += link.query('g30_observer',.30,keep)
    return {
        'lines':lines,
        'state':val(lines,r'R3H req=\\d+ state=(\\d+)',int,-1),
        'reason':val(lines,r'R3H req=\\d+ state=\\d+ reason=(\\d+)',int,-1),
        'coast':val(lines,r'coast=(\\d+)',int,-1),
        'valid':val(lines,r'FO76_R3I7 .* valid=(\\d+)',int,-1),
        'catch':val(lines,r'catch state=(\\d+)',int,-1),
        'catch_err':val(lines,r'catch state=\\d+ phase=\\d+ err=(-?\\d+)',int,None),
        'catch_step':val(lines,r'step_q4=(-?\\d+)',int,None),
    }

def run_push(link,phase,target,wait_s,hold_s,min_starts,expect_cal_before):
    link.log('='*68)
    link.log(f'PHASE {phase}: MCSDK RUN + PWM COAST; dann manueller Anschub.')
    link.set_rpm(0); link.poll(.25)
    before=status(link)
    if expect_cal_before is not None and before['cal']!=expect_cal_before:
        link.log(f'ABORT {phase}: cal={before["cal"]}, erwartet {expect_cal_before}')
        return False

    link.query('g30_pushstart arm',.35)
    coast=wait_for_true_coast(link,phase)
    if not coast or coast['mcstate']!=6 or coast['pwm_off']!=1 or coast['adc_ready']!=1 or coast['frames']<3:
        link.log(f'ABORT {phase}: kein RUN-Coast/ADC-Precheck. Motor NICHT anschieben.')
        link.set_rpm(0)
        link.query('g30_status',.5)
        return False

    link.log('RAD NOCH NICHT ANSCHIEBEN.')
    for n in (3,2,1):
        link.log(f'ANSCHIEBEN IN {n} ...')
        time.sleep(.55)
    link.log('\\aJETZT RAD VORWAERTS ANSCHIEBEN, etwa 1 Sekunde reicht.')
    link.log('PWM ist AUS. BEMF seedet Winkel; R3I7 fuehrt Catch-Drehzahl nach und blendet erst dann zum Observer.')
    link.set_rpm(target)

    deadline=time.monotonic()+wait_s
    locked=None
    next_diag=0.0
    good_confirm=0
    while time.monotonic()<deadline:
        now=time.monotonic()
        if now>=next_diag:
            st=status(link,keep=True)
            link.log(f'WAIT {phase}: mode={st["mode"]} cal={st["cal"]} started={st["started"]} starts={st["starts"]} mcstate={st["mcstate"]} pwm_off={st["pwm_off"]} frames={st["frames"]} edges={st["edges"]} dpp={st["dpp"]} erpm={st["erpm"]}')
            if st['started']==1 and st['starts']>=min_starts and st['mcstate']==6 and st['pwm_off']==0:
                cd=control_diag(link,keep=True)
                link.log(f'CATCH {phase}: tk_state={cd["state"]} reason={cd["reason"]} coast={cd["coast"]} valid={cd["valid"]} catch={cd["catch"]} err={cd["catch_err"]} step_q4={cd["catch_step"]}')
                if cd['coast']==1 or cd['state']==4:
                    link.log(f'FAIL {phase}: Observer-Catch fiel auf Coast/Fallback.')
                    link.set_rpm(0); link.poll(.3)
                    return False
                if cd['state']==3 and cd['coast']==0 and cd['valid']==1 and cd['catch']==0:
                    good_confirm+=1
                    if good_confirm>=2:
                        locked=st
                        break
                else:
                    good_confirm=0
            next_diag=now+.35
        link.poll(.06,keep_rpm=True)

    if not locked:
        link.set_rpm(0); link.poll(.4)
        link.log(f'FAIL {phase}: kein validierter Observer-Lock innerhalb des Fensters.')
        status(link); control_diag(link)
        return False

    link.log(f'*** {phase} OBSERVER LOCK: starts={locked["starts"]} cal={locked["cal"]} offset={locked["offset"]} ***')
    end=time.monotonic()+hold_s
    while time.monotonic()<end:
        link.set_rpm(target); link.poll(.10,keep_rpm=True)
        cd=control_diag(link,keep=True)
        if cd['coast']==1 or cd['state']==4 or cd['valid']!=1 or cd['catch']!=0:
            link.log(f'FAIL {phase}: Observer-Lock im Hold verloren.')
            link.set_rpm(0); link.poll(.3)
            return False

    link.log(f'{phase}: RPM=0, anschließend normaler Observer-Coast.')
    link.set_rpm(0); link.poll(2.0)
    status(link)
    control_diag(link)
    return True

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',default='COM9')
    ap.add_argument('--baud',type=int,default=115200)
    ap.add_argument('--target-erpm',type=int,default=1500)
    ap.add_argument('--wait',type=float,default=25.0)
    ap.add_argument('--hold',type=float,default=3.0)
    args=ap.parse_args()

    try: import serial
    except ImportError:
        print('pyserial fehlt. Einmal: py -m pip install pyserial',file=sys.stderr); return 2

    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    logfile=f'R3I7_PUSHSTART_{args.port}_{stamp}.log'.replace(':','_')
    link=None
    with open(logfile,'w',encoding='utf-8') as fp:
        try:
            ser=serial.Serial(args.port,args.baud,timeout=.03,write_timeout=1)
            time.sleep(.15); ser.reset_input_buffer()
            link=Link(ser,fp); link.log(f'OPEN {args.port} {args.baud} 8N1')
            pre=link.query('g30_status',.8)
            build=next((x for x in pre if x.startswith('Build: ')),'')
            if 'G30D-FO76-PUSHSTART-R3I7' not in build:
                link.log('ABORT: kein R3I7 Build erkannt.'); return 3
            if val(pre,r'fault_now=0x([0-9A-Fa-f]+)',lambda x:int(x,16),0xffff)!=0:
                link.log('ABORT: Fault aktiv.'); return 4

            link.query('g30_observer reset',.25)
            link.query('g30_pushstart off',.2)

            if not run_push(link,'A CALIBRATION',args.target_erpm,args.wait,args.hold,1,0):
                return 10
            time.sleep(.7)
            mid=status(link)
            if mid['cal']!=1:
                link.log('FAIL: Kalibrierung blieb nicht erhalten.'); return 11

            if not run_push(link,'B HALL-FREE SEED GATE',args.target_erpm,args.wait,args.hold,2,1):
                return 12

            link.set_rpm(0); link.poll(.7)
            end=[]
            end+=link.query('g30_pushstart status',.4)
            end+=link.query('g30_takeover status',.4)
            end+=link.query('g30_observer',.7)
            end+=link.query('top',1.0)
            starts=val(end,r'starts=(\d+)',int,0)
            maxcycles=val(end,r'Max Cycles: (\d+)',int,None)
            freeheap=val(end,r'Mem: \d+b Free: (\d+)b',int,None)
            link.log('='*68)
            link.log(f'FINAL starts={starts} max_cycles={maxcycles} heap_free={freeheap}')
            if starts>=2:
                link.log('RESULT: R3I7 PASS - echter Coast, Kalibrier-Push und zweiter BEMF-Seed erfolgreich.')
                link.log(f'LOG: {logfile}')
                return 0
            return 13
        except KeyboardInterrupt:
            if link:
                try: link.set_rpm(0); link.log('CTRL-C: RPM=0 gesendet')
                except Exception: pass
            return 130
        finally:
            if link:
                try: link.set_rpm(0); link.poll(.15); link.ser.close()
                except Exception: pass

if __name__=='__main__':
    raise SystemExit(main())
