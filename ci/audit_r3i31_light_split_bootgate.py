#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
pwr=(root/'common_files/src/task_pwr.c').read_text()
hdr=(root/'common_files/src/task_pwr.h').read_text()
dash=(root/'common_files/src/g30_dash_link.c').read_text()
defs=(root/'common_files/src/defines.h').read_text()
single=pwr[pwr.index('case SINGLE_PRESS'):pwr.index('case LONG_PRESS')]
checks={
 'build_id':'G30D-R3I31-LIGHT-SPLIT-BOOTGATE' in defs,
 'boot_gate_state':'static uint8_t pressed, pending, startup_armed;' in pwr,
 'boot_gate_release_arm':'if(!startup_armed)' in pwr and 'if(!down)' in pwr and 'startup_armed = 1u;' in pwr,
 'boot_gate_returns_no_press':'return NO_PRESS;' in pwr[pwr.index('if(!startup_armed)'):pwr.index('if(down && !pressed)')],
 'boot_gate_diag':'startup_armed' in hdr and 'bootArmed=%u' in dash,
 'single_toggles_front_state':'m365_to_display.light = !m365_to_display.light;' in single,
 'single_no_rear_gpio':'task_LED_set_brake_light' not in single and 'BRAKE_LIGHT_' not in single,
 'cmd64_0_100_retained':'status[2]=m365_to_display.light?100u:0u;' in dash,
 'button_diag_retained':'single_count++' in pwr and 'double_count++' in pwr and 'long_count++' in pwr,
 'double_250_retained':'<= 250u' in pwr and '> 250u' in pwr,
 'long_2500_retained':'held_ms >= 2500u' in pwr,
}
for k,v in checks.items(): print(f'{k}={int(v)}')
assert all(checks.values()), checks
body=pwr[pwr.index('void task_PWR(void *argument)'):pwr.index('void task_PWR_init')]
for forbidden in ('MCI_ExecSpeedRamp','MCI_StartMotor','MCI_StopMotor','MCI_SetCurrentReferences','PWMC_SwitchOnPWM','PWMC_SwitchOffPWM'):
    assert forbidden not in body, forbidden
print('R3I31 LIGHT-SPLIT BOOT-GATE AUDIT: PASS')
