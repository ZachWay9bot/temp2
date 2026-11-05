#!/usr/bin/env python3
import argparse,re,sys,time,os
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
            if self.b[0]==2: n=self.b[1]; h=2
            else:
                if len(self.b)<3: break
                n=(self.b[1]<<8)|self.b[2]; h=3
            total=h+n+3
            if len(self.b)<total: break
            p=bytes(self.b[:total]); del self.b[:total]
            if p[-1]!=3: continue
            pl=p[h:h+n]; rx=(p[h+n]<<8)|p[h+n+1]
            if crc16(pl)==rx: out.append(pl)
        return out
def query(ser,p,cmd,wait=.7):
    ser.write(frame(bytes((COMM_TERMINAL_CMD,))+cmd.encode())); ser.flush()
    end=time.monotonic()+wait; lines=[]
    while time.monotonic()<end:
        n=ser.in_waiting
        if n:
            for pl in p.feed(ser.read(n)):
                if pl and pl[0]==COMM_PRINT:
                    txt=pl[1:].decode(errors="replace").replace("\r","")
                    lines += [x for x in txt.split("\n") if x]
        else: time.sleep(.01)
    return lines
def num(s,key):
    m=re.search(rf"{key}=(\d+)",s); return int(m.group(1)) if m else None
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--port",default="COM9"); ap.add_argument("--seconds",type=int,default=18); a=ap.parse_args()
    try: import serial
    except ImportError: print("pyserial fehlt: py -m pip install pyserial"); return 2
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S"); os.makedirs("LOGS",exist_ok=True); log=os.path.join("LOGS",f"BMSPHY_V1_{stamp}.log")
    with open(log,"w",encoding="utf-8") as fp:
        ser=serial.Serial(a.port,115200,timeout=.03,write_timeout=1); time.sleep(.2); ser.reset_input_buffer(); p=Parser()
        def emit(x): print(x); fp.write(x+"\n"); fp.flush()
        for x in query(ser,p,"g30_status",.8): emit(x)
        b=query(ser,p,"g30_bmsphy",.8); [emit(x) for x in b]
        bline=next((x for x in b if x.startswith("BMSPHY samples=")),"")
        b10e0=num(bline,"pb10_edges") or 0; b11e0=num(bline,"pb11_edges") or 0
        b10l0=num(bline,"pb10_low") or 0; b11l0=num(bline,"pb11_low") or 0
        bw0=next((x for x in b if x.startswith("BMSPHY TXWIN_low=")),"")
        txw0=num(bw0,"TXWIN_low") or 0; txwe0=num(bw0,"TXWIN_edges") or 0
        rxw0=num(bw0,"RXWIN_low") or 0; rxwe0=num(bw0,"RXWIN_edges") or 0
        end=time.monotonic()+a.seconds
        while time.monotonic()<end:
            [emit(x) for x in query(ser,p,"g30_bms",.5)]
            time.sleep(.5)
        e=query(ser,p,"g30_bmsphy",.8); [emit(x) for x in e]
        eline=next((x for x in e if x.startswith("BMSPHY samples=")),"")
        b10e=(num(eline,"pb10_edges") or 0)-b10e0; b11e=(num(eline,"pb11_edges") or 0)-b11e0
        b10l=(num(eline,"pb10_low") or 0)-b10l0; b11l=(num(eline,"pb11_low") or 0)-b11l0
        ew=next((x for x in e if x.startswith("BMSPHY TXWIN_low=")),"")
        txw=(num(ew,"TXWIN_low") or 0)-txw0; txwe=(num(ew,"TXWIN_edges") or 0)-txwe0
        rxw=(num(ew,"RXWIN_low") or 0)-rxw0; rxwe=(num(ew,"RXWIN_edges") or 0)-rxwe0
        emit(f"DELTA hf_pb10_edges={b10e} hf_pb10_low={b10l} hf_pb11_edges={b11e} hf_pb11_low={b11l}")
        emit(f"DELTA txwin_low={txw} txwin_edges={txwe} rxwin_low={rxw} rxwin_edges={rxwe}")
        if txw>0 and rxw==0:
            emit("RESULT: TX_PAD_ACTIVE_RX_PAD_FLAT - PB10 sendet physisch am MCU-Pad, PB11 bleibt im Antwortfenster high.")
        elif txw>0 and rxw>0:
            emit("RESULT: TX_AND_RX_PAD_ACTIVITY - PB11 sieht physische Aktivitaet; USART/DMA ist dann der Hauptverdaechtige.")
        elif txw==0 and rxw>0:
            emit("RESULT: RX_PAD_ACTIVITY_TX_PAD_FLAT - RX lebt, TX-Pad/USART3-TX-Konfiguration pruefen.")
        else:
            emit("RESULT: NO_PAD_ACTIVITY - selbst das direkte TX/RX-Fenster sieht keine Low-Pegel.")
        emit("LOG: "+log); ser.close()
    return 0
if __name__=="__main__": raise SystemExit(main())
