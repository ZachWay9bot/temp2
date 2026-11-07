#!/usr/bin/env python3
from pathlib import Path
import re,sys
R=Path('SOURCE_KOXX3')
checks=[]
def ck(name,ok):
    checks.append((name,bool(ok))); print(f'{name}={"PASS" if ok else "FAIL"}')
def text(p): return (R/p).read_text()
d=text('common_files/src/defines.h')
g=text('common_files/src/g30_dash_link.c')
v=text('common_files/src/VescToSTM.c')
m=text('common_files/src/mc_tasks.c')
c=text('common_files/src/VescCommand.c')
t=text('common_files/src/terminal.c')
ck('IDENTITY','SHUD4-STRICT-DRIVE-V1' in d and 'G30_SHUD4_STRICT_DRIVETRAIN_V1 1' in d and 'G30_HALL_ROLLING_SYNC_V1 1' not in d)
ck('STRICT_DPC_CONSTANTS',all(x in g for x in ['55000*n*n)/(110*110)','shud4_slew(d->shud4.request_ma,d->shud4.target_ma,6500)','kph*313.0f']))
ck('STRICT_BRAKE_CONSTANTS',all(x in g for x in ['rate>945','5000 + b*(30000-5000)/130','target,500)','rate>500','request_ma,0,1500','rate>400']))
strict=g[g.index('/* STRICT SHUD4 slow-drive reconstruction.'):g.index('static unsigned rx_pos')]
ck('NO_SESC_DRIVE_SETTER_IN_STRICT','VescToSTM_set_current_rel_int' not in strict and 'g30_dash_r2_step' not in strict)
ck('DIRECT_REQUEST_ADAPTER',all(x in v for x in ['VescToSTM_g30_shud4_apply_request','MCI_SetCurrentReferences','PWMC_SwitchOffPWM']))
ck('HALL_STATE_PRESERVED_ON_REENABLE','Native SHUD4 keeps the Hall timing/interpolator alive' in v)
ck('NO_DUPLICATE_4KHZ_SLEW',re.search(r'#ifdef G30_SHUD4_STRICT_DRIVETRAIN_V1\s+.*?g30_drv126_final_q_slew_mc=qtarget;\s+int32_t qmc=qtarget;',m,re.S) is not None)
ck('VESC_MOTOR_COMMANDS_BLOCKED',c.count('g30_dash_link_strict_owns_motor()')==6)
ck('INTERPRETER_TERMINAL','g30_shud4' in t and 'g30_dash_link_shud4_print' in t)
ck('PROTECTION_SHELL_RETAINED','VescToSTM_get_fault()==FAULT_CODE_NONE' in g and 'app_is_output_disabled()' in g)
ck('NO_PROTECTION_BYPASS_PORT','central_error_latch' not in strict and 'VBUS_start_check' not in strict)
def clamp(x,a,b): return max(a,min(b,x))
def slew(c,t,s): return c+s if t-c>s else c-s if t-c<-s else t
def dpc(raw):
    n=clamp(raw-55,0,120); return 55000*n*n//12100
ck('DPC_VECTOR_55',dpc(55)==0)
ck('DPC_VECTOR_100',dpc(100)==9204)
ck('DPC_VECTOR_175',dpc(175)==65454)
ck('DPC_SLEW_VECTOR',slew(0,dpc(100),6500)==6500)
ck('RELEASE_SLEW_VECTOR',slew(10000,0,1500)==8500)
ck('BRAKE_SLEW_VECTOR',slew(0,-5000,500)==-500)
if not all(v for _,v in checks): sys.exit(2)
print('SHUD4_STRICT_DRIVETRAIN_V1_STATIC=PASS')
