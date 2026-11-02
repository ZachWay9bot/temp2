#!/usr/bin/env python3
"""R3I25 exact-scope audit against the R3I24 reconstructed source."""
from pathlib import Path
import sys
root=Path(sys.argv[1]); before=Path(sys.argv[2])
changes={
 'common_files/src/task_pwr.c': [
  ('begin within 250 ms;', 'begin within 500 ms;'),
  ('(uint32_t)(now - released_at) <= 250u)', '(uint32_t)(now - released_at) <= 500u)'),
  ('(uint32_t)(now - released_at) > 250u)', '(uint32_t)(now - released_at) > 500u)'),
 ],
 'common_files/src/g30_dash_link.c': [('status[2]=m365_to_display.light?100u:0u;', 'status[2]=m365_to_display.light?64u:0u;')],
 'common_files/src/defines.h': [('G30D-R3I24-DASH-MODE-SAFE', 'G30D-R3I25-DASH-LIGHT-BUTTON')],
}
for path, rules in changes.items():
 old=(before/path).read_text()
 new=(root/path).read_text()
 expected=old
 for a,b in rules:
  assert expected.count(a)==1, (path,a,'original occurrence')
  expected=expected.replace(a,b)
 assert expected==new, (path,'unexpected changes outside R3I25 scope')
 print('EXACT R3I24->R3I25 DIFF PASS:',path)
pwr=(root/'common_files/src/task_pwr.c').read_text()
dash=(root/'common_files/src/g30_dash_link.c').read_text()
defs=(root/'common_files/src/defines.h').read_text()
assert 'held_ms >= 2500u' in pwr
assert 'return LONG_PRESS;' in pwr
assert 'switch(m365_to_display.mode & 0x07u)' in pwr
assert 'status[2]=m365_to_display.light?64u:0u;' in dash
assert 'G30D-R3I25-DASH-LIGHT-BUTTON' in defs
start=pwr.index('void task_PWR('); end=pwr.index('void task_PWR_init',start)
body=pwr[start:end]
for forbidden in ('MCI_Exec','MCI_StartMotor','MCI_StopMotor','MCI_SetCurrentReferences','VescToSTM_set_','PWMC_SwitchOnPWM','PWMC_SwitchOffPWM'):
 assert forbidden not in body, forbidden
print('R3I25 DASH LIGHT + BUTTON AUDIT: PASS')
