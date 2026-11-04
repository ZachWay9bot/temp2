#!/usr/bin/env python3
from pathlib import Path
root=Path("SOURCE_KOXX3")
defs=(root/"common_files/src/defines.h").read_text()
led=(root/"common_files/src/task_LED.c").read_text()
term=(root/"common_files/src/terminal.c").read_text()
conf=(root/"common_files/src/conf_general.c").read_text()
vs=(root/"common_files/src/VescToSTM.c").read_text()
prod=(root/"common_files/inc/product.h").read_text()
assert 'SESC-MOTORPATH-SAFETY-V0.1A' in defs
assert 'g30_safety_iwdg_start' not in led
assert 'g30_safety_iwdg_feed' not in led
assert 'IWDG->KR' not in led
assert 'MP safety iwdg=OFF' in term
assert 'PWM_Handle_M1._Super.OverCurrentCycles = 0;' in conf
assert 'utils_map_int(temp, fp.temp_cut_start, fp.temp_cut_end, iq, 0)' in vs
assert '0.0, 0.95' in prod
print("NO_IWDG_RUNTIME=PASS")
print("OCP_THERMAL_DUTY_RETAINED=PASS")
