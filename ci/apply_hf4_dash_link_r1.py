#!/usr/bin/env python3
"""Add a telemetry-only G30 dashboard link to the exact HF4 source."""
from pathlib import Path
import hashlib,json,shutil,sys,difflib

root=Path(sys.argv[1] if len(sys.argv)>1 else 'SOURCE_KOXX3').resolve()
assets=Path(__file__).with_name('hf4_dash_link_r1')
if not assets.is_dir(): assets=Path(__file__).parent
before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file() and '.git' not in p.parts}
src=root/'common_files/src'

def once(p,old,new):
    data=p.read_text()
    assert data.count(old)==1,(str(p),old[:100],data.count(old))
    p.write_text(data.replace(old,new,1))

once(src/'defines.h','#define HW_NAME "G30D-FO76-PUSHSTART-R3I15HF4"',
     '#define HW_NAME "G30D-HF4-DASH-LINK-R1"')
once(src/'app.c','#include "timers.h"','#include "timers.h"\n#include "g30_dash_link.h"')
once(src/'app.c','\tswitch (appconf.app_to_use) {',
'''#ifdef G30P
    /* Dashboard R1 observes controls only. Never start the legacy ADC drive
     * task or bind VESC Tool to the dashboard UART. */
    g30_dash_link_start(&aux_uart);
    return;
#endif
\tswitch (appconf.app_to_use) {''')
once(src/'terminal.c','#include "g30_r3i_pushstart.h"',
     '#include "g30_r3i_pushstart.h"\n#include "g30_dash_link.h"')
once(src/'terminal.c','\tif (strcmp(argv[0], "ping") == 0) {',
'''    if (strcmp(argv[0], "g30dash") == 0) {
        g30_dash_link_print(phandle);
        return;
    }
\tif (strcmp(argv[0], "ping") == 0) {''')
project=root/'g30p/STM32CubeIDE/.project'
once(project,'\t</linkedResources>',
'''        <link>
            <name>Application/User/VESC/src/g30_dash_link.c</name>
            <type>1</type>
            <locationURI>PARENT-2-PROJECT_LOC/common_files/src/g30_dash_link.c</locationURI>
        </link>
\t</linkedResources>''')
for name in ('g30_dash_link.c','g30_dash_link.h','g30_dash_proto.h'):
    shutil.copyfile(assets/name,src/name)

after={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file() and '.git' not in p.parts}
changed=sorted(p for p in set(before)|set(after) if before.get(p)!=after.get(p))
allowed=['common_files/src/'+s for s in ('app.c','terminal.c','defines.h','g30_dash_link.c','g30_dash_link.h','g30_dash_proto.h')]
allowed+=['g30p/STM32CubeIDE/.project']
assert changed==sorted(allowed),(changed,allowed)
for name in ('VescToSTM.c','VescCommand.c','mc_tasks.c','g30_fo76_shadow.c','g30_r3i_pushstart.c','app_uartcomm.c','packet.c'):
    p='common_files/src/'+name
    assert before[p]==after[p],name
new_code=(src/'g30_dash_link.c').read_text()
for forbidden in ('VescToSTM_set_', 'VescToSTM_timeout_reset(', 'VescToSTM_g30_pushstart_command(', 'MCI_StartMotor(', 'xTimerStart('):
    assert forbidden not in new_code,forbidden
assert 'HAL_UART_Transmit(u,tx,' in new_code
assert 'HAL_UART_Transmit_DMA(' not in new_code
assert '->gState =' not in new_code
out=root.parent/'OUTPUT';out.mkdir(exist_ok=True)
audit={'base':'6c15e44c5f60b33a194c38d2a994b39c872a163d',
       'build':'G30D-HF4-DASH-LINK-R1','dashboard_motor_commands':False,
       'modified_files':changed,'unchanged_core_sha256':{p:hashlib.sha256(after[p]).hexdigest() for p in before if p.startswith('common_files/src/') and p not in changed}}
(out/'DASH_R1_CHANGE_AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n')
patch=''
for p in changed:
    patch+=''.join(difflib.unified_diff(before.get(p,b'').decode().splitlines(True),after[p].decode().splitlines(True),fromfile='a/'+p,tofile='b/'+p))
(out/'HF4_DASH_LINK_R1_FROM_FROZEN_HF4.patch').write_text(patch)
print('HF4 unchanged motor/observer/VESC source audit: PASS')
print('Dashboard R1 raw controls only; no dashboard motor commands')
