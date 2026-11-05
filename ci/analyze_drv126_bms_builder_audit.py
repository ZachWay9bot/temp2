#!/usr/bin/env python3
from pathlib import Path
import hashlib,struct,re
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM

BIN=Path("OUTPUT/DRV126_STOCK.bin")
data=BIN.read_bytes()
BASE=0x08001000
assert len(data)==30076
assert hashlib.sha256(data).hexdigest()=="3da93fb2eabfb6c46bf5d652f9317e186326bf1390967f90949eaab6a4b29c9f"

md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN)
md.detail=True
ins=list(md.disasm(data,BASE))
idx={i.address:n for n,i in enumerate(ins)}
BUILDER=0x08005288

calls=[]
for n,i in enumerate(ins):
    if i.mnemonic in ("bl","blx") and i.operands and i.operands[0].type==ARM_OP_IMM:
        if (i.operands[0].imm & ~1)==BUILDER:
            calls.append((n,i))

def val_from_recent(n,reg,limit=28):
    # Conservative: nearest simple immediate assignment before call, stop if register overwritten dynamically.
    for j in range(n-1,max(-1,n-limit-1),-1):
        i=ins[j]
        ops=i.op_str.replace(" ","")
        if re.match(rf"^(movs?|mov\.w){reg},#",ops):
            m=re.search(r"#(0x[0-9a-fA-F]+|\d+)",ops)
            return int(m.group(1),0) if m else None
        if re.match(rf"^(movs?|mov\.w){reg},r",ops) or re.match(rf"^ldr.*{reg},",ops) or re.match(rf"^ldrb.*{reg},",ops) or re.match(rf"^add.*{reg},",ops):
            return None
    return None

def window(n,before=24,after=5):
    return "\n".join(f"{x.address:08x}: {x.mnemonic:8s} {x.op_str}" for x in ins[max(0,n-before):min(len(ins),n+after+1)])

rows=[]
for n,i in calls:
    r0=val_from_recent(n,"r0")
    r1=val_from_recent(n,"r1")
    r2=val_from_recent(n,"r2")
    r3=val_from_recent(n,"r3")
    bms=(r0==0x20 and r1==0x22)
    rows.append((i.address,r0,r1,r2,r3,bms))

out=[]
out.append("EXACT_STOCK_DRV126_BMS_PACKET_BUILDER_AUDIT")
out.append("sha256=3da93fb2eabfb6c46bf5d652f9317e186326bf1390967f90949eaab6a4b29c9f")
out.append("builder=0x08005288 ABI: r0=src r1=dst r2=payloadLen r3=cmd stack0=arg stack4=payload stack8=channel")
out.append("")
out.append("callsite\tr0_src\tr1_dst\tr2_len\tr3_cmd\tbms_direct")
for a,r0,r1,r2,r3,bms in rows:
    fmt=lambda v:"?" if v is None else f"0x{v:02X}"
    out.append(f"0x{a:08X}\t{fmt(r0)}\t{fmt(r1)}\t{fmt(r2)}\t{fmt(r3)}\t{int(bms)}")

out.append("\n== BMS-directed windows ==")
for (n,i),(a,r0,r1,r2,r3,bms) in zip(calls,rows):
    if bms:
        out.append(f"\n-- 0x{a:08X} len={r2} cmd={r3} --")
        out.append(window(n,30,6))

# Explicit assertions for autonomous Stock126-originated READ30 sites already RE-validated.
text="\n".join(out)
for site in (0x08001BBC,0x080041FC):
    assert f"-- 0x{site:08X}" in text
    section=text.split(f"-- 0x{site:08X}",1)[1].split("\n-- ",1)[0]
    assert "movs     r1, #0x22" in section
    assert "movs     r0, #0x20" in section
    assert ("movs     r3, #1" in section or "mov      r2, r3" in section)
    assert "#0x30" in section
    assert "#0xc" in section

Path("OUTPUT/DRV126_BMS_BUILDER_AUDIT.txt").write_text(text)
print(text)
