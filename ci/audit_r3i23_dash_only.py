#!/usr/bin/env python3
from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else "SOURCE_KOXX3")
src=root/"common_files/src"
appu=(src/"app_uartcomm.c").read_text()
app=(src/"app.c").read_text()
pwr=(src/"task_pwr.c").read_text()
dash=(src/"g30_dash_link.c").read_text()
defs=(src/"defines.h").read_text()

def body(name):
    start=appu.index("void "+name+"(")
    nxt=appu.find("\nvoid ",start+5)
    if nxt<0: nxt=len(appu)
    return appu[start:nxt]

check=body("app_check_timer")
init=body("app_adc_init_timer")

checks={
 "build_id":"G30D-R3I23-DASH-ONLY" in defs,
 "g30_check_timer_noop":"#ifdef G30P" in check and "return;" in check.split("#else")[0],
 "g30_init_timer_noop":"#ifdef G30P" in init and "return;" in init.split("#else")[0],
 "legacy_timer_retained_other_targets":'xTimerCreate("ADC_UP"' in init.split("#else",1)[1],
 "dash_link_active":"g30_dash_link_start(&aux_uart);" in app,
 "g30_app_returns_before_legacy_switch":app.index("g30_dash_link_start(&aux_uart);") < app.index("switch (appconf.app_to_use)"),
 "mode_helpers_retained":"void app_adc_speed_mode" in appu and "m365_to_display.mode |= speed;" in appu,
 "temp_helpers_retained":"void app_adc_set_mode" in appu and "void app_adc_clear_mode" in appu,
 "button_mask_retained":"switch(m365_to_display.mode & 0x07u)" in pwr,
 "dash_control_retained":"g30_dash_r2_step" in dash and "VescToSTM_set_current_rel_int" in dash,
}
for k,v in checks.items(): print(f"{k}={int(bool(v))}")
assert all(checks.values()), [k for k,v in checks.items() if not v]
print("R3I23 DASH-ONLY SOURCE AUDIT: PASS")
print("G30 legacy ADC_UP creation/start disabled; mode/TEMP helpers retained")
