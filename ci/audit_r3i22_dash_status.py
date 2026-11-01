#!/usr/bin/env python3
from pathlib import Path
import re, sys, math

root=Path(sys.argv[1] if len(sys.argv)>1 else "SOURCE_KOXX3")
src=root/"common_files/src"
inc=root/"common_files/inc"

dash=(src/"g30_dash_link.c").read_text()
proto=(src/"g30_dash_proto.h").read_text()
app=(src/"app.c").read_text()
uart=(src/"app_uartcomm.c").read_text()
vesc=(src/"VescToSTM.c").read_text()
pwr=(src/"task_pwr.c").read_text()
defs=(inc/"mcconf_default.h").read_text()
nine=(src/"ninebot.h").read_text()

checks={
 "only_active_g30_dash_task": '#ifdef G30P' in app and 'g30_dash_link_start(&aux_uart);' in app and 'return;' in app[app.index('g30_dash_link_start(&aux_uart);'):app.index('#endif',app.index('g30_dash_link_start(&aux_uart);'))],
 "reply_only_on_cmd64": 'if(reply_pending && d->parser.state==0u && rd==rx_pos(d)) send_status(d);' in dash,
 "cmd65_no_reply": 'if(kind==64u)' in dash and 'else d->cmd65++' in dash,
 "status_mode": 'uint8_t status[6]={m365_to_display.mode,0,0,0,0,0};' in dash,
 "battery_source": 'VescToSTM_get_battery_level(0)' in dash,
 "battery_clamp": 'if(!isfinite(level)||level<0.0f) level=0.0f;' in dash and 'if(level>1.0f) level=1.0f;' in dash,
 "battery_percent_round": 'status[1]=(uint8_t)(100.0f*level+0.5f);' in dash,
 "speed_source_kmh": 'VescToSTM_get_speed()*3.6f' in dash,
 "speed_absolute": 'fabsf(VescToSTM_get_speed()*3.6f)' in dash,
 "speed_clamp": 'if(speed>255.0f) speed=255.0f;' in dash,
 "speed_round": 'status[4]=(uint8_t)(speed+0.5f);' in dash,
 "fault_raw_low_byte": 'status[5]=(uint8_t)(pMCI[M1]->pSTM->hFaultOccurred&0xFFu);' in dash,
 "beep_zero": 'uint8_t status[6]={m365_to_display.mode,0,0,0,0,0};' in dash and 'status[3]' not in dash,
 "frame_20_to_21_cmd64": 'out[3]=0x20;out[4]=0x21;out[5]=0x64;out[6]=0;' in proto,
 "mode_speed_bits_only": 'm365_to_display.mode &= 0xF8;' in uart and 'm365_to_display.mode |= speed;' in uart,
 "double_press_masks_upper_bits": 'switch(m365_to_display.mode & 0x07u)' in pwr,
 "30_physical_poles": '#define MCCONF_SI_MOTOR_POLES 30' in defs,
 "wheel_025m": re.search(r'#define MCCONF_SI_WHEEL_DIAMETER\s+0\.250',defs) is not None,
 "gear_1": re.search(r'#define MCCONF_SI_GEAR_RATIO\s+1\b',defs) is not None,
 "battery_10s": re.search(r'#define MCCONF_SI_BATTERY_CELLS\s+10\b',defs) is not None,
 "battery_6ah": re.search(r'#define MCCONF_SI_BATTERY_AH\s+6\.0',defs) is not None,
 "battery_liion": 'MCCONF_SI_BATTERY_TYPE' in defs and 'BATTERY_TYPE_LIION_3_0__4_2' in defs,
 "speed_uses_pole_pairs": 'VescToSTM_pole_pairs()' in vesc[vesc.index('float VescToSTM_get_speed'):vesc.index('}',vesc.index('float VescToSTM_get_speed'))+1],
 "legacy_light_comment_not_proof": 'if(MS->light)ui8_tx_buffer[8]=64;' in nine,
 "runtime_light_currently_100": 'status[2]=m365_to_display.light?100u:0u;' in dash,
}
for k,v in checks.items():
    print(f"{k}={int(bool(v))}")
assert all(checks.values()), [k for k,v in checks.items() if not v]

# Deterministic field-boundary expectations from current runtime formula.
def batt(level):
    if not math.isfinite(level) or level < 0: level=0.0
    if level > 1: level=1.0
    return int(100.0*level+0.5)
def speed(ms):
    kmh=abs(ms*3.6)
    if not math.isfinite(kmh) or kmh < 0: kmh=0.0
    if kmh > 255: kmh=255.0
    return int(kmh+0.5)

assert [batt(x) for x in (-1.0,0.0,0.004,0.005,0.499,0.5,0.999,1.0,2.0,float('nan'))] == [0,0,0,1,50,50,100,100,100,0]
assert speed(0)==0
assert speed(1.0)==4
assert speed(-1.0)==4
assert speed(10.0)==36
assert speed(1000.0)==255
assert speed(float('nan'))==0

print("R3I22 DASH STATUS SOURCE AUDIT: PASS")
print("battery=0..100 rounded; speed=abs(km/h) 0..255 rounded; fault=raw MCSDK low byte")
print("LIGHT UNRESOLVED: runtime currently emits 0/100; legacy comment mentions 0/64; no ON capture means no change is authorized")
