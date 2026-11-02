#!/usr/bin/env python3
from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else "SOURCE_KOXX3")
src=root/"common_files/src"
pwr=(src/"task_pwr.c").read_text()
defs=(src/"defines.h").read_text()

start=pwr.index("void task_PWR(")
end=pwr.index("\nvoid task_PWR_init", start)
body=pwr[start:end]

dstart=body.index("case DOUBLE_PRESS")
dend=body.index("} break ;", dstart)+len("} break ;")
double=body[dstart:dend]

forbidden=[
    "MCI_Exec",
    "MCI_StartMotor",
    "MCI_StopMotor",
    "MCI_SetCurrentReferences",
    "VescToSTM_set_",
    "PWMC_SwitchOnPWM",
    "PWMC_SwitchOffPWM",
]
checks={
    "build_id":"G30D-R3I24-DASH-MODE-SAFE" in defs,
    "mode_cycle_retained":"switch(m365_to_display.mode & 0x07u)" in double,
    "current_limit_retained":"lo_current_max_scale" in double,
    "speed_limit_retained":"lo_max_erpm" in double,
    "no_motor_command_in_double":all(x not in double for x in forbidden),
    "no_motor_command_any_button_path":all(x not in body for x in forbidden),
    "vesctostm_header_not_needed":'#include "VescToSTM.h"' not in pwr,
}
for k,v in checks.items():
    print(f"{k}={int(bool(v))}")
assert all(checks.values()), [k for k,v in checks.items() if not v]
print("R3I24 DASH-MODE-SAFE AUDIT: PASS")
print("button path changes mode/current/speed LIMITS only; no motor command emitted")
