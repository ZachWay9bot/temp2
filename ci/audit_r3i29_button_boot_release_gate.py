#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
pwr=(root/'common_files/src/task_pwr.c').read_text()
main=(root/'g30p/Src/main.c').read_text()
dash=(root/'common_files/src/g30_dash_link.c').read_text()
defs=(root/'common_files/src/defines.h').read_text()
checks={
 'build_id':'G30D-R3I29-BUTTON-BOOT-GATE' in defs,
 'pullup_retained':'GPIO_InitStruct.Pull = GPIO_PULLUP;' in main,
 'active_low_retained':'HAL_GPIO_ReadPin(PWR_BTN_GPIO_Port, PWR_BTN_Pin) == GPIO_PIN_RESET' in pwr,
 'poweroff_active_low_retained':'while(HAL_GPIO_ReadPin(PWR_BTN_GPIO_Port, PWR_BTN_Pin) == GPIO_PIN_RESET);' in pwr,
 'startup_gate_declared':'static uint8_t pressed, pending, startup_armed;' in pwr,
 'startup_release_arms':'if(!startup_armed)' in pwr and 'if(!down)' in pwr and 'startup_armed = 1u;' in pwr,
 'startup_returns_no_press':'startup_armed = 1u;' in pwr and 'return NO_PRESS;' in pwr[pwr.index('if(!startup_armed)'):pwr.index('if(down && !pressed)')],
 'r3i24_light_field_retained':'status[2]=m365_to_display.light?100u:0u;' in dash,
 'double_250_retained':'<= 250u' in pwr and '> 250u' in pwr,
 'long_2500_retained':'held_ms >= 2500u' in pwr,
}
for k,v in checks.items(): print(f'{k}={int(v)}')
assert all(checks.values()), checks
print('R3I29 BOOT-RELEASE GATE AUDIT: PASS')
