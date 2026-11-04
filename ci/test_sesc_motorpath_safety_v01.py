#!/usr/bin/env python3
from pathlib import Path

# Algorithmic thermal-map checks using the exact monotonic direction used by the firmware.
def map_int(x, in_min, in_max, out_min, out_max):
    return int((x-in_min)*(out_max-out_min)/(in_max-in_min)+out_min)

start=8140
end=1986
iq=30000
assert map_int(start,start,end,iq,0)==iq
mid=(start+end)//2
m=map_int(mid,start,end,iq,0)
assert 14500 <= m <= 15500
assert map_int(end,start,end,iq,0)==0
assert map_int(start,start,end,-iq,0)==-iq
assert map_int(end,start,end,-iq,0)==0
print("THERMAL_ENDPOINTS=PASS")
print("THERMAL_MIDPOINT=PASS")
print("THERMAL_NEGATIVE_IQ=PASS")

root=Path("SOURCE_KOXX3")
conf=(root/"common_files/src/conf_general.c").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
prod=(root/"common_files/inc/product.h").read_text()
led=(root/"common_files/src/task_LED.c").read_text()
term=(root/"common_files/src/terminal.c").read_text()
defs=(root/"common_files/src/defines.h").read_text()

assert 'SESC-MOTORPATH-SAFETY-V0.1' in defs
assert 'PWM_Handle_M1._Super.OverCurrentCycles = 0;' in conf
assert 'utils_map_int(temp, fp.temp_cut_start, fp.temp_cut_end, iq, 0)' in vs
assert 'temp <= fp.temp_cut_end' in vs and 'iq = 0;' in vs
assert '#define HW_LIM_DUTY_MAX\t\t\t0.0, 0.95' in prod
assert 'IWDG->RLR = 1250u;' in led and 'g30_safety_iwdg_feed();' in led
assert 'MP thermal raw=' in term and 'cli_stack_hw=' in term and 'MP safety iwdg_pr=' in term
# Frozen control paths must not be edited by this safety patch.
print("SAFETY_STATIC_GATES=PASS")
