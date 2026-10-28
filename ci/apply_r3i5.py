from pathlib import Path

ROOT=Path("SOURCE_KOXX3")
SRC=ROOT/"common_files/src"

def one(path, old, new, label):
    p=path; s=p.read_text(); n=s.count(old)
    if n!=1: raise SystemExit(f"{label}: expected one anchor, got {n}")
    p.write_text(s.replace(old,new,1))

one(SRC/"defines.h",
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I3"',
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I5"',
    "build id")

# Keep the proven MCSDK RUN state. Push-start arm only removes PWM so the wheel
# coasts freely; after BEMF seed we re-enable PWM directly in RUN.
p=SRC/"terminal.c"; s=p.read_text()
old='''        if(argc==2 && strcmp(argv[1],"arm")==0){
            VescToSTM_set_speed(0);
            (void)MCI_StopMotor( pMCI[M1] );
            VescToSTM_pwm_stop();
            g30_fo76_request_takeover(0u);
            g30_r3i_request_arm(1u);
            commands_printf(phandle,"R3I2 ARM: forced MCSDK STOP + PWM OFF; passive BEMF sampling only after coast");
'''
new='''        if(argc==2 && strcmp(argv[1],"arm")==0){
            VescToSTM_pwm_stop();
            g30_fo76_request_takeover(0u);
            g30_r3i_request_arm(1u);
            commands_printf(phandle,"R3I5 ARM: keep MCSDK RUN, force PWM OFF for coast; BEMF seed re-enables PWM directly");
'''
if old not in s: raise SystemExit("terminal arm anchor")
s=s.replace(old,new,1)
s=s.replace('FO76_R3I3 pushstart_sensorless=1','FO76_R3I5 pushstart_sensorless=1',1)
p.write_text(s)

# Replace the R3I2 STOP->IDLE->START restart helper with a direct RUN/PWM resume.
p=SRC/"mc_tasks.c"; s=p.read_text()
old='''#ifdef G30P
  if(g30_r3i_start_pending() && StateM1==IDLE)
  {
    if(MCI_StartMotor( pMCI[M1] ))
    {
      g30_r3i_start_consumed();
    }
  }
#endif
'''
new='''#ifdef G30P
  if(g30_r3i_start_pending() && StateM1==RUN)
  {
    VescToSTM_prepare_sensorless_start();
    VescToSTM_pwm_start();
    if(!PWM_Handle_M1._Super.PWM_off)
    {
      g30_r3i_start_consumed();
    }
  }
#endif
'''
if old not in s: raise SystemExit("restart helper anchor")
s=s.replace(old,new,1)
p.write_text(s)

print("R3I5 transform applied")
