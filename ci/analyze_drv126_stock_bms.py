#!/usr/bin/env python3
from pathlib import Path
import struct, hashlib
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

BIN=Path("OUTPUT/DRV126_STOCK.bin")
data=BIN.read_bytes()
assert len(data)==30076
sha=hashlib.sha256(data).hexdigest()
assert sha=="3da93fb2eabfb6c46bf5d652f9317e186326bf1390967f90949eaab6a4b29c9f"
BASE=0x08001000

md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN)
md.detail=True
md.skipdata=True
ins=list(md.disasm(data,BASE))

# Heuristic function starts: push containing lr, plus reset/vector-known entry points.
starts={BASE}
for i in ins:
    if i.mnemonic in ("push","stmdb") and "lr" in i.op_str:
        starts.add(i.address)
starts=sorted(starts)

def func_start(addr):
    lo=BASE
    for s in starts:
        if s>addr: break
        lo=s
    return lo

# Resolve Thumb LDR literals.
literals=[]
for i in ins:
    if i.mnemonic.startswith("ldr") and i.operands and len(i.operands)>=2:
        op=i.operands[1]
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            pc=(i.address+4)&~3
            a=pc+op.mem.disp
            off=a-BASE
            if 0<=off<=len(data)-4:
                v=struct.unpack_from("<I",data,off)[0]
                literals.append((i.address,func_start(i.address),a,v,i.mnemonic,i.op_str))

USART3=0x40004800
DMA_CH2=0x4002001c
DMA_CH3=0x40020030
interesting_periph={USART3,DMA_CH2,DMA_CH3}
periph=[x for x in literals if x[3] in interesting_periph or (x[3]&0xfffff000)==0x40004000]

# Collect instructions that use protocol constants.
const_hits=[]
want={0x5a,0xa5,0x20,0x21,0x22,0x23,0x30,0x10,0x34,0x01,0x04,0x39,0x57,0x59}
for i in ins:
    vals=[]
    for op in i.operands:
        if op.type==ARM_OP_IMM:
            vals.append(op.imm & 0xffffffff)
    for v in vals:
        if v in want:
            const_hits.append((i.address,func_start(i.address),v,i.mnemonic,i.op_str))

# BL call graph.
calls=[]
for i in ins:
    if i.mnemonic in ("bl","blx") and i.operands and i.operands[0].type==ARM_OP_IMM:
        calls.append((i.address,func_start(i.address),i.operands[0].imm & ~1))

def window(addr,before=24,after=64):
    return "\n".join(f"{i.address:08x}: {i.mnemonic:8s} {i.op_str}" for i in ins if addr-before<=i.address<=addr+after)

out=[]
out.append(f"SHA256={sha} bytes={len(data)} base=0x{BASE:08x}")
out.append("\n== USART / DMA literal references ==")
for x in periph:
    out.append(f"ins=0x{x[0]:08x} func~=0x{x[1]:08x} lit=0x{x[2]:08x} value=0x{x[3]:08x} {x[4]} {x[5]}")

out.append("\n== Protocol immediate clusters by function ==")
from collections import defaultdict
by=defaultdict(list)
for h in const_hits: by[h[1]].append(h)
for f,hs in sorted(by.items()):
    vals={h[2] for h in hs}
    # prioritize clusters containing BMS addr and status-like register/command
    if 0x22 in vals and (0x30 in vals or 0x10 in vals or 0x34 in vals or 0x20 in vals):
        out.append(f"FUNC~ 0x{f:08x} constants="+",".join(f"{v:02x}" for v in sorted(vals)))
        for h in hs[:80]: out.append(f"  0x{h[0]:08x}: imm=0x{h[2]:x} {h[3]} {h[4]}")

# Known windows from prior RE report plus parser offsets noted by independent analysis.
known=[0x08003fec,0x08004070,0x08008238,0x08006936,0x08006c56,0x08006f7c]
out.append("\n== Known windows ==")
for a in known:
    out.append(f"\n-- window 0x{a:08x} --\n"+window(a,64,160))

# Find functions that access USART3 directly and their callers.
u3_funcs=sorted({x[1] for x in periph if x[3]==USART3})
out.append("\n== USART3 functions and direct callers ==")
for f in u3_funcs:
    out.append(f"USART3_FUNC~=0x{f:08x}")
    out.append(window(f,0,220))
    for c in calls:
        if c[2]==f:
            out.append(f"  CALLER ins=0x{c[0]:08x} func~=0x{c[1]:08x}")
            out.append(window(c[0],100,140))

Path("OUTPUT/DRV126_BMS_RE.txt").write_text("\n".join(out))
Path("OUTPUT/DRV126_BMS_CALLS.tsv").write_text(
    "callsite\tcaller\ttarget\n"+"\n".join(f"{a:08x}\t{f:08x}\t{t:08x}" for a,f,t in calls)
)
print("DRV126_STOCK_BMS_RE=PASS")
print("USART3_FUNCS", [hex(x) for x in u3_funcs])
