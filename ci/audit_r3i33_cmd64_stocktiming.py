#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
dash=(root/'common_files/src/g30_dash_link.c').read_text()
pwr=(root/'common_files/src/task_pwr.c').read_text()
defs=(root/'common_files/src/defines.h').read_text()
single=pwr[pwr.index('case SINGLE_PRESS'):pwr.index('case LONG_PRESS')]
checks={
 'build_id':'G30D-R3I33-CMD64-STOCKTIMING' in defs,
 'stock_byte1_zero':'status[1]=0u;' in dash,
 'light_stock_0_100':'status[2]=m365_to_display.light?100u:0u;' in dash,
 'stock_timing_delay':'vTaskDelay(2);' in dash,
 'send_after_delay':dash.index('vTaskDelay(2);') < dash.index('send_status(d);', dash.index('vTaskDelay(2);')),
 'boot_gate_retained':'startup_armed' in pwr and 'if(!startup_armed)' in pwr,
 'single_front_toggle_retained':'m365_to_display.light = !m365_to_display.light;' in single,
 'rear_gpio_not_on_single':'task_LED_set_brake_light' not in single,
}
for k,v in checks.items(): print(f'{k}={int(v)}')
assert all(checks.values()), checks
print('R3I33 CMD64 STOCK-TIMING AUDIT: PASS')
