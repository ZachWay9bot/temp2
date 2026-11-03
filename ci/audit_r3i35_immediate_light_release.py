#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
pwr=(root/'common_files/src/task_pwr.c').read_text()
dash=(root/'common_files/src/g30_dash_link.c').read_text()
defs=(root/'common_files/src/defines.h').read_text()
single=pwr[pwr.index('case SINGLE_PRESS'):pwr.index('case LONG_PRESS')]
event=pwr[pwr.index('eButtonEvent getButtonEvent()'):pwr.index('void task_PWR_get_button_diag')]
checks={
 'build_id':'G30D-R3I35-IMMEDIATE-LIGHT' in defs,
 'r3i34_bit0_retained':'status[2]=m365_to_display.light?1u:0u;' in dash,
 'battery_byte_retained':'status[1]=(uint8_t)(100.0f*level+0.5f);' in dash,
 'preview_state':'light_previewed' in event,
 'toggle_on_first_release':'m365_to_display.light = !m365_to_display.light;' in event[event.index('if(held_ms >= 30u)'):event.index('} else if(pending == 2u)')],
 'cancel_on_second_press':'if(light_previewed)' in event[event.index('if(down && !pressed)'):event.index('} else if(!down && pressed)')],
 'restore_on_bounce':'if(!light_previewed)' in event,
 'single_no_second_toggle':'m365_to_display.light = !m365_to_display.light;' not in single,
 'double_retained':'return DOUBLE_PRESS;' in event,
 'long_retained':'return LONG_PRESS;' in event and 'held_ms >= 2500u' in event,
 'rear_gpio_still_absent':'task_LED_set_brake_light' not in single,
 'no_r3i33_delay':'vTaskDelay(2);' not in dash,
}
for k,v in checks.items(): print(f'{k}={int(v)}')
assert all(checks.values()), checks
print('R3I35 IMMEDIATE LIGHT RELEASE AUDIT: PASS')
