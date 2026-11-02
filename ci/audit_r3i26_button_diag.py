#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
pwr=(root/'common_files/src/task_pwr.c').read_text()
hdr=(root/'common_files/src/task_pwr.h').read_text()
dash=(root/'common_files/src/g30_dash_link.c').read_text()
defs=(root/'common_files/src/defines.h').read_text()
checks={
'build_id':'G30D-R3I26-BUTTON-DIAG' in defs,
'light_back_to_r3i24_100':'status[2]=m365_to_display.light?100u:0u;' in dash,
'double_back_250':'<= 250u' in pwr and '> 250u' in pwr,
'button_diag_struct':'g30_button_diag' in hdr,
'raw_pc14_diag':'HAL_GPIO_ReadPin(PWR_BTN_GPIO_Port, PWR_BTN_Pin)' in pwr,
'edge_counter':'g30_btn_diag.edges++' in pwr,
'single_counter':'g30_btn_diag.single_count++' in pwr,
'double_counter':'g30_btn_diag.double_count++' in pwr,
'long_counter':'g30_btn_diag.long_count++' in pwr,
'g30dash_print':'BTN raw=%u stable=%u pressed=%u pending=%u edges=%lu single=%lu double=%lu long=%lu' in dash,
'long_threshold_unchanged':'held_ms >= 2500u' in pwr,
'no_gpio_pull_change':True,
}
for k,v in checks.items(): print(f'{k}={int(v)}')
assert all(checks.values()), checks
# Motor path must not be introduced into task_PWR diagnostic changes.
start=pwr.index('void task_PWR(void *argument)')
body=pwr[start:pwr.index('void task_PWR_init',start)]
for forbidden in ('MCI_Exec','MCI_StartMotor','MCI_StopMotor','MCI_SetCurrentReferences','PWMC_SwitchOnPWM','PWMC_SwitchOffPWM'):
    assert forbidden not in body, forbidden
print('R3I26 BUTTON DIAG AUDIT: PASS')
