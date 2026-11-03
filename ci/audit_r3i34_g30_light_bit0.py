#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
dash=(root/'common_files/src/g30_dash_link.c').read_text()
pwr=(root/'common_files/src/task_pwr.c').read_text()
defs=(root/'common_files/src/defines.h').read_text()
single=pwr[pwr.index('case SINGLE_PRESS'):pwr.index('case LONG_PRESS')]
checks={
 'build_id':'G30D-R3I34-G30-LIGHT-BIT0' in defs,
 'battery_byte_retained':'status[1]=(uint8_t)(100.0f*level+0.5f);' in dash,
 'no_stockbyte_zero':'status[1]=0u;' not in dash,
 'g30_light_bit0':'status[2]=m365_to_display.light?1u:0u;' in dash,
 'no_light_100':'status[2]=m365_to_display.light?100u:0u;' not in dash,
 'boot_gate_retained':'startup_armed' in pwr and 'if(!startup_armed)' in pwr,
 'single_front_toggle_retained':'m365_to_display.light = !m365_to_display.light;' in single,
 'rear_gpio_not_on_single':'task_LED_set_brake_light' not in single,
 'no_timing_experiment':'vTaskDelay(2);' not in dash,
}
for k,v in checks.items(): print(f'{k}={int(v)}')
assert all(checks.values()), checks
print('R3I34 G30 LIGHT BIT0 AUDIT: PASS')
