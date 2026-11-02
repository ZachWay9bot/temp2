#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
dash=(root/'common_files/src/g30_dash_link.c').read_text()
defs=(root/'common_files/src/defines.h').read_text()
pwr=(root/'common_files/src/task_pwr.c').read_text()
checks={
 'build_id':'G30D-R3I27-LIGHT-BOOL' in defs,
 'light_bool_0_1':'status[2]=m365_to_display.light?1u:0u;' in dash,
 'no_light_100':'status[2]=m365_to_display.light?100u:0u;' not in dash,
 'no_light_64':'status[2]=m365_to_display.light?64u:0u;' not in dash,
 'button_250ms_retained':'<=250u' in pwr.replace(' ','') and '>250u' in pwr.replace(' ',''),
 'long_2500_retained':'held_ms>=2500u' in pwr.replace(' ',''),
}
for k,v in checks.items(): print(f'{k}={int(v)}')
assert all(checks.values()), checks
print('R3I27 LIGHT BOOL AUDIT: PASS')
