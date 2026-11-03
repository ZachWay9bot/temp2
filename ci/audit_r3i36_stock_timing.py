#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
dash=(root/'common_files/src/g30_dash_link.c').read_text()
pwr=(root/'common_files/src/task_pwr.c').read_text()
defs=(root/'common_files/src/defines.h').read_text()
single=pwr[pwr.index('case SINGLE_PRESS'):pwr.index('case LONG_PRESS')]
checks={
 'build_id':'G30D-R3I36-STOCK-TIMING' in defs,
 'battery_byte_r3i34':'status[1]=(uint8_t)(100.0f*level+0.5f);' in dash,
 'light_bit0_r3i34':'status[2]=m365_to_display.light?1u:0u;' in dash,
 'no_stockbyte_zero':'status[1]=0u;' not in dash,
 'stock_timing_delay':'vTaskDelay(2);' in dash,
 'delay_before_send':dash.index('vTaskDelay(2);') < dash.index('send_status(d);',dash.index('vTaskDelay(2);')),
 'r3i31_button_behavior':'m365_to_display.light = !m365_to_display.light;' in single,
 'no_r3i35_preview':'light_previewed' not in pwr,
 'boot_gate_retained':'startup_armed' in pwr and 'if(!startup_armed)' in pwr,
 'rear_gpio_still_absent':'task_LED_set_brake_light' not in single,
}
for k,v in checks.items(): print(f'{k}={int(v)}')
assert all(checks.values()), checks
print('R3I36 STOCK TIMING ON R3I34 AUDIT: PASS')
