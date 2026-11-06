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
