#!/usr/bin/env python3
import hashlib, urllib.request, re, json
from pathlib import Path
from collections import Counter, defaultdict
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

URL="https://raw.githubusercontent.com/scooterhacking/firmware/master/max/DRV/1.2.6.bin"
EXPECTED="3da93fb2eabfb6c46bf5d652f9317e186326bf1390967f90949eaab6a4b29c9f"
BASE=0x08001000
OUT=Path("OUTPUT"); OUT.mkdir(exist_ok=True)
binp=OUT/"DRV126_STOCK.bin"
data=urllib.request.urlopen(URL, timeout=30).read()
binp.write_bytes(data)
sha=hashlib.sha256(data).hexdigest()
assert sha==EXPECTED,(sha,EXPECTED)
assert len(data)==30076,len(data)

md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN)
md.detail=True
ins=list(md.disasm(data,BASE))
byaddr={i.address:i for i in ins}

def fmt(i):
    return f"{i.address:08X}: {i.bytes.hex():<10} {i.mnemonic:<7} {i.op_str}"

def window(addr,before=14,after=8):
    idx=min(range(len(ins)),key=lambda j:abs(ins[j].address-addr))
    return ins[max(0,idx-before):min(len(ins),idx+after+1)]

report=[]
report.append(f"DRV126 sha256={sha} size={len(data)} base={BASE:08X}")
for a in (0x080041E8,0x08001BAA):
    report.append(f"\n=== KNOWN STOCK BMS REQUEST REGION {a:08X} ===")
    report += [fmt(i) for i in window(a,18,18)]

# collect BL/BLX direct targets
calls=defaultdict(list)
for i in ins:
    if i.mnemonic in ("bl","blx"):
        m=re.match(r"#?(0x[0-9a-fA-F]+|[0-9]+)$",i.op_str.strip())
        if m:
            try:t=int(m.group(1),0)
            except:continue
            calls[t].append(i.address)

report.append("\n=== CALL TARGETS REFERENCED IN KNOWN REGIONS ===")
known_targets=set()
for target,sites in calls.items():
    if any(abs(s-0x080041E8)<0x40 or abs(s-0x08001BAA)<0x40 for s in sites):
        known_targets.add(target)
        report.append(f"target={target:08X} calls={len(sites)} sites="+",".join(f"{s:08X}" for s in sites[:50]))

# Context heuristic for all calls to candidate targets.
# We do NOT claim ABI values automatically; dump enough context to manually verify.
for target in sorted(known_targets):
    report.append(f"\n=== ALL CONTEXTS FOR CANDIDATE TARGET {target:08X} ===")
    for s in calls[target]:
        report.append(f"\n-- callsite {s:08X} --")
        report += [fmt(i) for i in window(s,16,2)]

# broader heuristic: callsites whose prior instructions contain immediates 0x20 and 0x22
report.append("\n=== HEURISTIC BMS-LIKE CALLS (prior window contains #0x20 and #0x22) ===")
hits=[]
for target,sites in calls.items():
    for s in sites:
        ws=window(s,18,1)
        txt=" | ".join(i.op_str.lower() for i in ws[:-1])
        has20=("#0x20" in txt or "#32" in txt)
        has22=("#0x22" in txt or "#34" in txt)
        if has20 and has22:
            hits.append((s,target,ws))
            report.append(f"\n-- callsite {s:08X} target {target:08X} --")
            report += [fmt(i) for i in ws]

# Search for immediate 'movs r?, #1/#2' near candidate target calls and summarize.
report.append("\n=== CANDIDATE CMD IMMEDIATES NEAR BMS BUILDER CALLS ===")
for target in sorted(known_targets):
    for s in calls[target]:
        ws=window(s,20,1)
        ims=[]
        for i in ws:
            if i.mnemonic.startswith("mov") and re.search(r"#(0x)?[12]$",i.op_str):
                ims.append(fmt(i))
        if ims:
            report.append(f"callsite {s:08X}:")
            report += ["  "+x for x in ims]

(OUT/"DRV126_BMS_STATIC_AUDIT.txt").write_text("\n".join(report),encoding="utf-8")
(OUT/"DRV126_BMS_STATIC_AUDIT.json").write_text(json.dumps({
    "sha256":sha,"size":len(data),"base":hex(BASE),
    "known_targets":{hex(t):[hex(x) for x in calls[t]] for t in sorted(known_targets)},
    "heuristic_hit_count":len(hits)
},indent=2),encoding="utf-8")
print("\n".join(report[:120]))
print(f"REPORT={OUT/'DRV126_BMS_STATIC_AUDIT.txt'}")


# Robust halfword-aligned BL scan. Linear disassembly can lose sync when it crosses
# literal pools, so inspect every possible Thumb halfword independently.
all_bl=[]
for off in range(0,len(data)-4,2):
    addr=BASE+off
    one=list(md.disasm(data[off:off+4],addr,count=1))
    if not one: continue
    i=one[0]
    if i.mnemonic not in ("bl","blx"): continue
    m=re.match(r"#?(0x[0-9a-fA-F]+|[0-9]+)$",i.op_str.strip())
    if not m: continue
    try:t=int(m.group(1),0)
    except: continue
    all_bl.append((addr,t,fmt(i)))

report.append("\n=== ROBUST HALFWORD BL XREFS TO PACKET BUILDER 08005288 ===")
x5288=[x for x in all_bl if x[1]==0x08005288]
for x in x5288: report.append(x[2])
report.append(f"xrefs_to_08005288={len(x5288)}")

def targeted(start,end):
    # Decode starting at every halfword and retain valid instruction starts.
    out={}
    for off in range(max(0,start-BASE), min(len(data)-2,end-BASE),2):
        a=BASE+off
        one=list(md.disasm(data[off:off+8],a,count=1))
        if one: out[a]=one[0]
    return [out[a] for a in sorted(out)]

for a,b,label in [(0x080041B0,0x08004230,"KNOWN_41E8"),
                  (0x08001B80,0x08001BD0,"KNOWN_1BAA"),
                  (0x08005280,0x08005480,"BUILDER_5288")]:
    report.append(f"\n=== TARGETED {label} {a:08X}..{b:08X} ===")
    report += [fmt(i) for i in targeted(a,b)]

report.append("\n=== ALL LIKELY ESC20->BMS22 PACKET BUILDER CALLS ===")
# For each builder xref, decode 0x30 bytes immediately before the call on halfword boundaries.
for site,target,_ in x5288:
    report.append(f"\n-- builder call {site:08X} --")
    report += [fmt(i) for i in targeted(site-0x30,site+6)]

report.append("\n=== STOCK-GENERATED BMS WRITE CHECK ===")
# ABI verified at 0x08001BBC: r0=src, r1=dst, r2=payloadLen, r3=cmd,
# stack[0]=arg, stack[4]=payload ptr, stack[8]=channel/context.
# A stock-generated BMS WRITE would therefore require a builder call with
# r0=0x20,r1=0x22 and r3=0x02 immediately before BL 0x08005288.
write_candidates=[]
for site,target,_ in x5288:
    ctx=targeted(site-0x40,site+2)
    textctx="\n".join(fmt(i) for i in ctx)
    has20=any(i.mnemonic.startswith("mov") and i.op_str.replace(" ","") in ("r0,#0x20","r0,#32") for i in ctx)
    has22=any(i.mnemonic.startswith("mov") and i.op_str.replace(" ","") in ("r1,#0x22","r1,#34") for i in ctx)
    cmd2=any(i.mnemonic.startswith("mov") and i.op_str.replace(" ","") in ("r3,#2","r3,#0x2") for i in ctx)
    if has20 and has22 and cmd2:
        write_candidates.append(site)
        report.append(f"WRITE_CANDIDATE {site:08X}\n{textctx}")
report.append(f"stock_generated_bms_write_candidates={len(write_candidates)}")
report.append(f"stock_generated_bms_packet_builder_calls={len(x5288)}")
if len(x5288)==1 and not write_candidates:
    report.append("CONCLUSION_STATIC: only one direct stock-generated call to packet builder 0x08005288; it is READ cmd=0x01 to BMS 0x22, arg=0x30, payloadLen=1, payload[0]=0x0C. No direct stock-generated BMS WRITE call found.")

(OUT/"DRV126_BMS_STATIC_AUDIT.txt").write_text("\n".join(report),encoding="utf-8")
