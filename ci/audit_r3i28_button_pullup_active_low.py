#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
pwr=(root/'common_files/src/task_pwr.c').read_text()
main=(root/'g30p/Src/main.c').read_text()
dash=(root/'common_files/src/g30_dash_link.c').read_text()
defs=(root/'common_files/src/defines.h').read_text()
checks={
 'build_id':'G30D-R3I28-BUTTON-PULLUP-LOW' in defs,
 'pc14_pullup':'GPIO_InitStruct.Pin = PWR_BTN_Pin;' in main and 'GPIO_InitStruct.Pull = GPIO_PULLUP;' in main[main.index('GPIO_InitStruct.Pin = PWR_BTN_Pin;'):main.index('HAL_GPIO_Init(PWR_BTN_GPIO_Port',main.index('GPIO_InitStruct.Pin = PWR_BTN_Pin;'))+60],
 'button_active_low':'HAL_GPIO_ReadPin(PWR_BTN_GPIO_Port, PWR_BTN_Pin) == GPIO_PIN_RESET' in pwr,
 'poweroff_active_low_wait':'while(HAL_GPIO_ReadPin(PWR_BTN_GPIO_Port, PWR_BTN_Pin) == GPIO_PIN_RESET);' in pwr,
 'r3i24_light_field_retained':'status[2]=m365_to_display.light?100u:0u;' in dash,
 'double_250_retained':'<= 250u' in pwr and '> 250u' in pwr,
 'long_2500_retained':'held_ms >= 2500u' in pwr,
}
for k,v in checks.items(): print(f'{k}={int(v)}')
assert all(checks.values()), checks
start=pwr.index('void task_PWR(void *argument)')
body=pwr[start:pwr.index('void task_PWR_init',start)]
for forbidden in ('MCI_Exec','MCI_StartMotor','MCI_StopMotor','MCI_SetCurrentReferences','PWMC_SwitchOnPWM','PWMC_SwitchOffPWM'):
    assert forbidden not in body, forbidden
print('R3I28 BUTTON PULLUP/ACTIVE-LOW AUDIT: PASS')
