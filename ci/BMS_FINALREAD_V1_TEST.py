#!/usr/bin/env python3
import argparse,re,time,os
from datetime import datetime
COMM_TERMINAL_CMD=20
COMM_PRINT=21

def crc16(data):
    crc=0
    for b in data:
        x=((crc>>8)&0xff)^b; x^=x>>4
        crc=((crc<<8)^(x<<12)^(x<<5)^x)&0xffff
    return crc

def frame(payload):
    n=len(payload); head=bytes((2,n)) if n<=255 else bytes((3,(n>>8)&255,n&255))
    c=crc16(payload); return head+payload+bytes((c>>8,c&255,3))

class Parser:
    def __init__(self): self.b=bytearray()
    def feed(self,d):
        self.b.extend(d); out=[]
        while self.b:
            while self.b and self.b[0] not in (2,3): del self.b[0]
            if len(self.b)<2: break
            if self.b[0]==2: n=self.b[1];h=2
            else:
                if len(self.b)<3: break
                n=(self.b[1]<<8)|self.b[2];h=3
            total=h+n+3
            if len(self.b)<total: break
            pkt=bytes(self.b[:total]);del self.b[:total]
            if pkt[-1]!=3: continue
            pl=pkt[h:h+n];rx=(pkt[h+n]<<8)|pkt[h+n+1]
            if crc16(pl)==rx: out.append(pl)
        return out

def query(ser,p,cmd,wait=.7):
    ser.write(frame(bytes((COMM_TERMINAL_CMD,))+cmd.encode()));ser.flush()
    end=time.monotonic()+wait;lines=[]
    while time.monotonic()<end:
        n=ser.in_waiting
        if n:
            for pl in p.feed(ser.read(n)):
                if pl and pl[0]==COMM_PRINT:
                    lines += [x for x in pl[1:].decode(errors='replace').replace('\r','').split('\n') if x]
        else: time.sleep(.01)
    return lines

def num(line,key,signed=False):
    m=re.search(rf'{re.escape(key)}=(-?\d+)',line)
    return int(m.group(1)) if m else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',default='COM9');ap.add_argument('--seconds',type=int,default=16);a=ap.parse_args()
    try: import serial
    except ImportError:
        print('pyserial fehlt: py -m pip install pyserial');return 2
    os.makedirs('LOGS',exist_ok=True)
    log=os.path.join('LOGS','BMS_FINALREAD_V1_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.log')
    ser=serial.Serial(a.port,115200,timeout=.03,write_timeout=1);p=Parser();time.sleep(.25);ser.reset_input_buffer()
    with open(log,'w',encoding='utf-8') as fp:
        def emit(x): print(x,flush=True);fp.write(x+'\n');fp.flush()
        st=query(ser,p,'g30_status',.8);[emit(x) for x in st]
        build=next((x for x in st if x.startswith('Build: ')),'')
        if 'SESC-DRV126-POWERCORE6500-BMS-FINALREAD-V1' not in build:
            emit('ABORT: falscher Build');ser.close();return 3
        phy=query(ser,p,'g30_bmsphy',.8);[emit(x) for x in phy]
        lock=next((x for x in phy if x.startswith('BMSPOWERLOCK enabled=1')),'')
        if not lock or num(lock,'moe')!=0:
            emit('ABORT: Powerlock/MOE nicht sicher');ser.close();return 4

        best=[]
        end=time.monotonic()+a.seconds
        while time.monotonic()<end:
            lines=query(ser,p,'g30_bms',.65);[emit(x) for x in lines]
            head=next((x for x in lines if x.startswith('BMS final=1')),'')
            live=next((x for x in lines if x.startswith('BMS live ')),'')
            cells=next((x for x in lines if x.startswith('BMS cells=')),'')
            if head and live and cells:
                fresh=num(head,'fresh') or 0
                age=num(head,'statusAge')
                cage=num(head,'cellsAge')
                pack=num(live,'pack')
                soc=num(live,'soc')
                mn=num(cells,'min');mx=num(cells,'max');delta=num(cells,'delta')
                if fresh==1 and age is not None and age<500 and cage is not None and cage<2000 and pack and 25000<=pack<=45000 and soc is not None and 0<=soc<=100 and mn and mx and 2500<=mn<=4500 and 2500<=mx<=4500 and delta is not None and delta<1000:
                    best=lines;break
            time.sleep(.25)

        phy2=query(ser,p,'g30_bmsphy',.8);[emit(x) for x in phy2]
        lock2=next((x for x in phy2 if x.startswith('BMSPOWERLOCK enabled=1')),'')
        if not lock2 or num(lock2,'moe')!=0:
            emit('RESULT: FAIL_POWERLOCK');ser.close();return 5
        if best:
            emit('RESULT: PASS_BMS_FINALREAD - 115200 Stock READ30 + cells + decode plausible, MOE stayed 0')
            rc=0
        else:
            emit('RESULT: FAIL_BMS_FINALREAD - telemetry did not become fresh/plausible')
            rc=6
        emit('LOG: '+log)
    ser.close();return rc

if __name__=='__main__': raise SystemExit(main())
