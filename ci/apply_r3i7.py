from pathlib import Path

ROOT=Path("SOURCE_KOXX3/common_files/src")

def one(name, old, new, label):
    p=ROOT/name
    s=p.read_text()
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"{label}: expected one anchor, got {n}")
    p.write_text(s.replace(old,new,1))

one("defines.h",
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I6"',
    '#define HW_NAME "G30D-FO76-PUSHSTART-R3I7"',
    "build id")

# Expose catch speed for hardware diagnostics.
one("g30_fo76_shadow.h",
'''uint16_t g30_fo76_catch_phase(void);
int16_t g30_fo76_catch_error(void);
uint16_t g30_fo76_catch_ticks(void);
''',
'''uint16_t g30_fo76_catch_phase(void);
int16_t g30_fo76_catch_error(void);
uint16_t g30_fo76_catch_ticks(void);
int16_t g30_fo76_catch_step_q4(void);
''',
"catch speed diag api")

p=ROOT/"g30_fo76_shadow.c"
s=p.read_text()

# Track catch frequency from the observer's phase DELTA while keeping BEMF-seeded
# angle independent. This compensates real wheel acceleration/deceleration after
# the human releases the wheel, without handing angle ownership to the observer.
old='''        takeover_step_foc_q4=(int16_t)(((int32_t)takeover_step_foc_q4*3 + delta)/4);
'''
new='''        takeover_step_foc_q4=(int16_t)(((int32_t)takeover_step_foc_q4*3 + delta)/4);
        if(sensorless_external && sensorless_catch_state){
            int16_t obs_step=takeover_step_foc_q4;
            /* Physical FWD is negative. Reject wild startup derivatives; then
             * slew catch frequency toward the filtered observer frequency.
             * Angle itself remains the independent BEMF-seeded predictor. */
            if(obs_step < -768 && obs_step > -8192){
                int32_t diff=(int32_t)obs_step-(int32_t)sensorless_catch_step_q4;
                if(diff>512)diff=512;
                else if(diff< -512)diff=-512;
                sensorless_catch_step_q4=(int16_t)((int32_t)sensorless_catch_step_q4 + diff/4);
            }
        }
'''
if old not in s: raise SystemExit("observer speed update anchor missing")
s=s.replace(old,new,1)

# Timeout may only latch once. R3I6 repeatedly incremented fallback count on each
# FOC tick after timeout while waiting for the medium task to coast.
old='''            if(sensorless_catch_ticks>G30_R3I6_CATCH_TIMEOUT_FOC){
                takeover_latch_coast(G30_TK_FB_INVALID);
                takeover_control_phase=catch_phase;
                return catch_phase;
            }
'''
new='''            if(sensorless_catch_ticks>G30_R3I6_CATCH_TIMEOUT_FOC){
                if(!takeover_coast_request) takeover_latch_coast(G30_TK_FB_INVALID);
                takeover_control_phase=catch_phase;
                return catch_phase;
            }
'''
if old not in s: raise SystemExit("catch timeout anchor missing")
s=s.replace(old,new,1)

old='''uint16_t g30_fo76_catch_ticks(void){return sensorless_catch_ticks;}
'''
new='''uint16_t g30_fo76_catch_ticks(void){return sensorless_catch_ticks;}
int16_t g30_fo76_catch_step_q4(void){return sensorless_catch_step_q4;}
'''
if old not in s: raise SystemExit("catch diag impl anchor missing")
s=s.replace(old,new,1)
p.write_text(s)

# A second push in the same boot must be possible after the normal observer
# coast moved MCSDK to IDLE. Arm first blocks PWM, clears the old sensorless
# trajectory/coast latch, then restarts MCSDK at zero speed if necessary.
p=ROOT/"terminal.c"
s=p.read_text()
old='''        if(argc==2 && strcmp(argv[1],"arm")==0){
            VescToSTM_pwm_stop();
            g30_fo76_request_takeover(0u);
            g30_r3i_request_arm(1u);
            commands_printf(phandle,"R3I6 ARM: RUN-coast; BEMF predictor catches rotor before observer blend");
'''
new='''        if(argc==2 && strcmp(argv[1],"arm")==0){
            VescToSTM_pwm_stop();
            g30_fo76_sensorless_clear();
            g30_fo76_request_takeover(0u);
            g30_r3i_request_arm(1u);
            if(STM_GetState(&STM[M1])==IDLE){
                MCI_ExecSpeedRamp(pMCI[M1],0,0);
                (void)MCI_StartMotor(pMCI[M1]);
            }
            commands_printf(phandle,"R3I7 ARM: PWM blocked; IDLE auto-restarts at zero; BEMF angle + observer frequency catch");
'''
if old not in s: raise SystemExit("terminal arm anchor missing")
s=s.replace(old,new,1)
s=s.replace('FO76_R3I6 pushstart_sensorless=1','FO76_R3I7 pushstart_sensorless=1',1)

old='''        commands_printf(phandle, "catch state=%u phase=%u err=%d ticks=%u",
            (unsigned)g30_fo76_catch_state(),(unsigned)g30_fo76_catch_phase(),
            (int)g30_fo76_catch_error(),(unsigned)g30_fo76_catch_ticks());
'''
new='''        commands_printf(phandle, "catch state=%u phase=%u err=%d ticks=%u step_q4=%d",
            (unsigned)g30_fo76_catch_state(),(unsigned)g30_fo76_catch_phase(),
            (int)g30_fo76_catch_error(),(unsigned)g30_fo76_catch_ticks(),
            (int)g30_fo76_catch_step_q4());
'''
if old not in s: raise SystemExit("terminal catch diag anchor missing")
s=s.replace(old,new,1)
p.write_text(s)

print("R3I7 transform applied")
